
from openai import OpenAI
import tiktoken

import multiprocessing

"""
We use a "separation of concerns principle:
1) "naked" API calls as a function...
2) ... called by a function that manages timeout using multiprocessing...
3) ... called by a function that manages dynamic chunking and proto-memory.
"""


#######################################################################################################
def OAI_direct_call_v2(return_dict, message, oai_key, **kwargs):
    """
    Sends a single "naked" API call to OpenAI with optional formats.

    note the input format for message:
    message=[
        {"role": "developer", "content": "You are a helpful ..."},
        {"role": "user", "content": " Etc ..."}
    ],

    kwargs relevant to this function:
        model
        temperature
        tk_encoding_name
        structured_output_switch
        structured_output_schema
    other kwargs:
        max_tk = max_tk
        max_time_out
        max_attempts
    """
    # add kwargs as this continues to evolve
    model=kwargs.get('model','gpt-4o-mini')
    temperature=kwargs.get('temperature', 1.0)
    structured_output_switch = kwargs.get('structured_output_switch', False)
    structured_output_schema = kwargs.get('structured_output_schema')  # no default!

    # We create a client object locally - this may slow things down a bit, but compartmentalizes the code
    client = OpenAI(api_key=oai_key)

    try:
        if structured_output_switch:
            # for a reference, see
            # https://platform.openai.com/docs/guides/structured-outputs?context=with_parse#examples

            completion = client.beta.chat.completions.parse(
                model = model,
                messages = message,  # note it must be a list with dictionaries inside [{"role": "user", "content": prompt},]
                temperature = temperature,
                response_format = structured_output_schema,
                )
            response = completion.choices[0].message.parsed

        else:
            completion = client.chat.completions.create(
                model = model, 
                messages = message, 
                temperature = temperature
                )
            response = completion.choices[0].message   # NB: response = {"role": "assistant","content": "something"}

        return_dict[0] = {'response': response, 'error': ''}
        
    except Exception as e:
        # Handle other exceptions
        return_dict[0] = {'response': f"Error: {str(e)}", 'error': str(e)}



#############################################################
def OAI_ringfenced_call_v2(message, oai_key, **kwargs):
    """
    Makes a single ring-fenced API call to OpenAI and manages a timeout mechanism.

    kwargs relevant to this function:
        max_time_out
        max_attempts
    other kwargs:
        model
        temperature
        tk_encoding_name
        structured_output_switch
        structured_output_schema
        max_tk
    """
    # time (s) between failed OAI calls
    max_time_out = kwargs.get('max_time_out', 20)

    print(f'max_time_out at ringfence = {max_time_out}')

    max_attempts = kwargs.get('max_attempts', 3)

    # We will use multiprocess to control for the request time to Open AI's API; 
    # if it takes too long, we stop the request and try again. 
    manager = multiprocessing.Manager()
    return_dict = manager.dict()

    attempts = 1
    OK_flag = False
    while OK_flag == False:
        try:
            p = multiprocessing.Process(
                target=OAI_direct_call_v2, 
                name="OAI_direct_call_v2", 
                args=(return_dict, message, oai_key),
                kwargs=kwargs
                )
            p.start()
        
            p.join(max_time_out) # waits a maximum of max_time_out seconds for a call ("time out")   
            
            if p.is_alive() and attempts <= max_attempts:
                # Timed out - kill the process and try again
                p.terminate()
                p.join()
                OK_flag = False # re-confirm that is must try again
                attempts += 1
            elif p.is_alive() and attempts > max_attempts:
                p.terminate()
                p.join()
                response=""
                error_msg = "timeout max attempts"
                OK_flag = True
            else:
                # It is not hanging: it either worked as expected or returned an error
                response_data = return_dict.values()[0]
                response = response_data['response']
                error_msg = response_data['error']
                OK_flag = True

            
        except Exception as str_err:
            response=f"Error: {str_err}"
            error_msg = "abort"
            OK_flag = True
    
    return(response, error_msg)
    


def call_AI_OAI(assistant, oai_key, **kwargs):
    """
    Simple 'wrapper function' that opens up the assistant and puts the information that the 
    other functions need at the right place
    assistant is an object that has the following things:
    variables:
    -- structured_output_switch (boolean)

    variables (as **kwargs --> assistants defined defaults, in case the instantiation does not set these values)
    -- model
    -- max_tk
    -- tk_encoding_name
    -- temperature

    methods: 
    -- generate_developer_prompt
    -- generate_developer_prompt_memory
    -- generate_user_prompt

    classes:
    if using structured output, this class will be there
    --- SOClass  (--> follows pydantic BaseModel)

    possible kwargs that influences the results (used by functions down the chain):
        max_time_out
        max_attempts
    """


    developer_prompt = assistant.generate_developer_prompt()
    user_prompt = assistant.generate_user_prompt()

    structured_output_switch = assistant.structured_output_switch

    if structured_output_switch:
        structured_output_schema = assistant.SOClass
    else:
        structured_output_schema = ""

    model = assistant.model
    max_tk = assistant.max_tk
    max_time_out = assistant.max_time_out
    tk_encoding_name = assistant.tk_encoding_name
    temperature = assistant.temperature


    # check the size of the prompt, just to avoid errors
    size_developer_prompt = how_many_tokens(developer_prompt, tk_encoding_name)
    size_user_prompt = how_many_tokens(user_prompt, tk_encoding_name)
    check_size = size_developer_prompt + size_user_prompt
    if check_size >= max_tk:
        print ("Prompt longer than max_tk - aborting")
        cut_point = max_tk - (size_developer_prompt + 100)
        user_prompt = user_prompt[0:cut_point]
        #return

    OK_flag = False  # we use this for error-handling
    counter = 1
    while OK_flag == False:

        message=[
            {"role":"developer", "content":developer_prompt}, 
            {"role":"user", "content":user_prompt}
            ]
        
        #print(f"\n\n message: {message}")

        response, error = OAI_ringfenced_call_v2(message, 
                                                 oai_key,
                                                 model = model,
                                                 max_tk = max_tk,
                                                 max_time_out = max_time_out,
                                                 tk_encoding_name = tk_encoding_name,
                                                 temperature = temperature,
                                                 structured_output_switch = structured_output_switch,
                                                 structured_output_schema = structured_output_schema,
                                                 **kwargs)

        if error == '':
            # It worked out, lets finish it
            OK_flag = True
            
        elif error == 'abort':
            # stop the whole thing
            print(f"There was an abort call, stopping it with error: {response}")
            OK_flag = True

        else:
            # there was an error but not an abort call: try this chunk again
            print(f"Trying again (no chunking), but there was an error: {error} {response}")
            if counter < 4:
                OK_flag = False
                counter += 1
            else:
                OK_flag = True

    if structured_output_switch:
        # NB: response = {..., "text_output": "something", ...}
        # send out the response **object**
        return(response)
    else:
        # NB: response = {"role": "assistant","content": "something"}
        # send out the response text
        return(response.content)



##### Supporting functions  #####

###################################
def how_many_tokens(text: str, encoding_name: str) -> int:
    """
    Calculates the number of tokens in a text string using a specified encoding.

    Parameters:
        text (str): The input string.
        encoding_name (str): The name of the encoding to use (e.g., "cl100k_base").

    Returns:
        int: The number of tokens in the string.
    """
    encoding = tiktoken.get_encoding(encoding_name)
    return len(encoding.encode(text))



