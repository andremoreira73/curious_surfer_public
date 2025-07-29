
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
def OAI_direct_call(return_dict, model, message, oai_key, **kwargs):
    """
    Sends a single "naked" API call to OpenAI with optional formats.

    note the input format for message:
    message=[
        {"role": "developer", "content": "You are a helpful ..."},
        {"role": "user", "content": " Etc ..."}
    ],
    """
    # add kwargs as this continues to evolve
    structured_output_switch = kwargs.get('structured_output_switch', False)
    structured_output_schema = kwargs.get('structured_output_schema')  # no default!
    temperature = kwargs.get('temperature', 1.0)

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
def OAI_ringfenced_call(model, message, oai_key, **kwargs):
    """
    Makes a single ring-fenced API call to OpenAI and manages a timeout mechanism.

    """
    # time (s) between failed OAI calls
    max_time_out = kwargs.get('max_time_out', 20)
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
                target=OAI_direct_call, 
                name="OAI_direct_call", 
                args=(return_dict, model, message, oai_key),
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
    


################################################
def call_OAI_GPT(developer_prompt_dict, user_prompt, model, oai_key, **kwargs):
    """
    Processes a text using a prompt and calls an LLM with chunking and a proto-memory capability if needed.

    If using structured outputs, you MUST have the text output field (corresponding to a summary, commentary, etc.) 
    field called "text_output", as it will be used for further processing within this function

    developer_prompt_dict is a dictionary: {"simple":"", "memory":""})
    user_prompt is the text we will process
    """
    max_tk = kwargs.get('max_tk', 128000)   # as of Jan 2025 
    tk_encoding_name = kwargs.get('tk_encoding_name', 'cl100k_base')  # as of Jan 2025
    structured_output_switch = kwargs.get('structured_output_switch', False)
    
    # Developer (introductory) prompt, assuming we will not need the proto-memory
    developer_prompt = developer_prompt_dict.get('simple')

    # check how the prompt size looks like - we do it piece by piece to ensure that the result is clean
    size_developer_prompt = how_many_tokens(developer_prompt, tk_encoding_name)
    size_user_prompt = how_many_tokens(user_prompt, tk_encoding_name)
    
    check_size = size_developer_prompt + size_user_prompt


    #
    # Todo: handle errors
    #
    OK_flag = False  # we use this for error-handling
    while OK_flag == False:

        # check if this needs chunking or not
        if check_size < max_tk:
            print("Not chunking")
            # no chunking, go for it!
            message=[
                {"role":"developer", "content":developer_prompt}, 
                {"role":"user", "content":user_prompt}
                ]
            
            #print(f"\n\n message: {message}")

            response, error = OAI_ringfenced_call(model, message, oai_key, **kwargs)

            if error == '':
                # It worked out, lets finish it
                OK_flag = True
                
            elif error == 'abort':
                # stop the whole thing
                print(f"There was an abort call, stopping it with error: {response}")
                OK_flag = True

            else:
                # there was an error but not an abort call: try this chunk again
                print(f"Trying again (no chunking), but there was an error: {error}")
                OK_flag = False

        else:
            print("Working on a longer text, using chunking...")
            # note that the LLM will see the <developer prompt> + <proto-memory> + <chunk of user prompt>

            # this is the "memory intro prompt", but still WITHOUT memory!
            developer_prompt = developer_prompt_dict.get('memory')
            # reset the proto-memory, in case we need it
            encoding = tiktoken.get_encoding(tk_encoding_name)

            # build the first message that will be passed to the LLM
            # encode: convert to tokens // decode: convert back to text
            developer_prompt_tokens = encoding.encode(developer_prompt)
            developer_prompt_token_count = len(developer_prompt_tokens)

            user_prompt_tokens = encoding.encode(user_prompt)
            user_prompt_token_count = len(user_prompt_tokens)
                
            token_buffer = 2500

            idx = 0  # pointer
            proto_memory = ""
            ll_proto_memory = []  # we will use this to store all the memories and create a final result
            end_point_tokens = user_prompt_token_count
            
            while idx < end_point_tokens:
                print(f"idx pointer at {idx}, finishes when reach {end_point_tokens}")
                # 1. How many tokens does memory currently have?
                memory_token_count = how_many_tokens(proto_memory, tk_encoding_name)

                # 2. Figure out how many tokens we can afford for this chunk
                max_chunk_tokens = max_tk - developer_prompt_token_count - memory_token_count - token_buffer
                if max_chunk_tokens <= 0:
                    print("[ERROR] developer prompt +  memory exceed the maximum token limit. Aborting.")
                    if structured_output_switch:
                        # send out the dictionary that we have at this moment
                        return(response)
                    else:
                        # send out the content that we have at this moment
                        return(response.content)

                # 3. Find how many tokens from text fit into `max_chunk_tokens`
                #    We'll pick as many tokens as we can until we approach the limit.
                chunk_start = idx
                chunk_end = chunk_start  # We'll move chunk_end forward
                while chunk_end < end_point_tokens:
                    current_chunk_size = chunk_end - chunk_start + 1
                    # If adding one more token exceeds the limit, break
                    if current_chunk_size > max_chunk_tokens:
                        break
                    chunk_end += 1
                
                # chunk_end is now the first index *not* included
                sub_chunk_tokens = user_prompt_tokens[chunk_start:chunk_end]

                # Re-encode to string for sending to OpenAI
                sub_chunk_text = encoding.decode(sub_chunk_tokens)

                # 4. Build our message and call the LLM
                sub_prompt = f"§§§Memory§§§\n{proto_memory}\n§§§End of Memory§§§\n{sub_chunk_text}"
                message=[
                    {"role":"developer", "content":developer_prompt}, 
                    {"role":"user", "content":sub_prompt}
                    ]
                #print(message)
                response, error = OAI_ringfenced_call(model, message, oai_key, **kwargs)

                if error == '':
                    # It worked out for this chunk...
                    idx = chunk_end  # advance pointer
                    if structured_output_switch:
                        # NB: response = {..., "text_output": "something", ...}
                        proto_memory = response.text_output
                    else:
                        # NB: response = {"role": "assistant","content": "something"}
                        proto_memory = response.content
                    ll_proto_memory.append(proto_memory)
                elif error == 'abort':
                    # stop the whole thing
                    print(f"There was an abort call, stopping it with error: {response}")
                    idx = end_point_tokens + 1
                else:
                    # there was an error but not an abort call: try this chunk again
                    # (no change to the pointer idx)
                    print(f"Repeating chunk {idx}, but there was an error: {response}")
            
            # Now we put together all the memories and do another round - 
            # will it need chunking again? if so, this will continue for a while...
            # if not, then we get our final result based on all those memories
            user_prompt = ' '.join(ll_proto_memory)
            print(f"\n\nNew user prompt:\n{user_prompt}\n\n")
            # Developer (introductory) prompt, assuming we will not need the proto-memory
            developer_prompt = developer_prompt_dict.get('simple')

            # check how the prompt size looks like - we do it piece by piece to ensure that the result is clean
            size_developer_prompt = how_many_tokens(developer_prompt, tk_encoding_name)
            size_user_prompt = how_many_tokens(user_prompt, tk_encoding_name)
            
            check_size = size_developer_prompt + size_user_prompt
            
 
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



