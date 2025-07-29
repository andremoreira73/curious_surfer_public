
import requests
from requests.exceptions import Timeout, RequestException

from bs4 import BeautifulSoup

from typing import Tuple, Optional

import readability
from html2text import HTML2Text

from datetime import datetime

import re



############################################################################################
def scrape_and_check_spdr(this_url, SB_endpoint, SB_key, **kwargs):
    """
    returns a status and the text, if available

    status can be 'time out', 'clutter' or 'OK'
    """

    # Parameters for ScrapingBee API
    headers = {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    }  # adding headers to get the pages to think this is coming from a "normal surfer"
    
    params = {
        'api_key': SB_key,
        'url': this_url,
        'block_ads': 'True',
        'render_js': 'True',
        'wait': '5000'
    }

    try:
        # use a ring-fence here in case the response time is too long
        # note that response_status can be "OK" or "Time out"
        response, response_status = make_request_with_retries(SB_endpoint, params, headers,
                                                              kwargs.get('max_retries', 3), 
                                                              kwargs.get('timeout_duration', 20))

        if response_status == 'Time out':
            stat = 'time out'
            extracted_text = 'Not available'
            return(stat, extracted_text)
        else:    
            raw_html = response.text

            #extracted_text = extract_content(raw_html)
            # We will try something new here: pass the html as it is, no cleaning
            extracted_text = raw_html

            if not extracted_text:
                return ('clutter', 'Not available')

            if not is_meaningful_content(extracted_text):
                return ('clutter', 'Not available')

            #print(f"Final cleaned_text (first 500 chars):\n{cleaned_text[:500]}")

            #is_content_good = check_content_quality_v2(extracted_text, oai_key, **kwargs)
            #if not is_content_good:
            #    return ('clutter', 'Not available')

            return ('OK', extracted_text)

    except Exception as e:
        print(f"Error processing {this_url}: {str(e)}")
        return ('clutter', 'Not available')

    


######################################################
def extract_content(raw_html: str) -> Tuple[Optional[str], Optional[datetime]]:
    """
    Attempts to extract the visible content and publication date from raw_html using multiple methods.
    """
    extracted_text = None
    article_date = None

    # 1.
    try:
        print("Trying to extract with BeautifulSoup")
        #print(raw_html)
        
        extracted_text = parse_text_after_scraping(raw_html)

        print(f"Extracted text (100 chars): {extracted_text[0:100]}")
    
        '''
        # 2. If no text, try readability-lxml
        if not extracted_text:
            print("Trying to extract with readability-lxml")
            extracted_text = extract_with_readability_v2(raw_html)
        '''

        return extracted_text
    
    except Exception as e:
        print(f"Error during extraction: {e}")
        return None



###################################################################
def is_meaningful_content_OLD(text: str, min_words: int = 100) -> bool:
    """
    Check if content meets basic quality criteria.
    
    Args:
        text: The text to analyze
        min_words: Minimum number of words required (default 100)
    
    Returns:
        bool: True if content meets quality criteria
    """
    if not text or len(text.strip()) < 200:  # Minimum character length
        return False
    words = len(text.split())
    return words >= min_words and not is_boilerplate_heavy(text)


# Improved is_meaningful_content function with job-specific patterns
def is_meaningful_content(text: str, min_words: int = 80) -> bool:
    """
    Enhanced check if content meets quality criteria for job listings.
    
    Args:
        text: The text to analyze
        min_words: Minimum number of words required (reduced to 80 from 100)
    
    Returns:
        bool: True if content meets quality criteria
    """
    if not text or len(text.strip()) < 150:  # Reduced minimum character length
        return False
        
    # Job-specific keywords that indicate useful content
    job_indicators = [
        "position", "vacancy", "responsibilities", "qualifications", 
        "experience", "skills", "apply", "application", "interim", 
        "manager", "management", "project", "lead", "director", "head of",
        "stellenangebot", "karriere", "bewerbung", "tätigkeiten", "aufgaben"
    ]
    
    # Check for job-specific patterns
    text_lower = text.lower()
    job_pattern_matches = sum(1 for pattern in job_indicators if pattern in text_lower)
    
    words = len(text.split())
    return (words >= min_words and not is_boilerplate_heavy(text)) or job_pattern_matches >= 2






############################################
def is_boilerplate_heavy_OLD(text: str) -> bool:
    """
    Check if text is dominated by boilerplate content.
    
    Args:
        text: The text to analyze
    
    Returns:
        bool: True if text contains too much boilerplate
    """
    boilerplate_patterns = [
        r'cookie[s]?\s+policy',
        r'privacy\s+policy',
        r'terms\s+of\s+service',
        r'subscribe|subscription',
        r'sign\s+up|login',
        r'advertisement',
        r'please\s+enable\s+javascript'
    ]
    pattern = '|'.join(boilerplate_patterns)
    matches = len(re.findall(pattern, text.lower()))
    text_length = len(text.split())
    return matches > 3 or (matches > 0 and text_length < 200)


# Updated is_boilerplate_heavy function with better filtering
def is_boilerplate_heavy(text: str) -> bool:
    """
    Improved check if text is dominated by boilerplate content.
    
    Args:
        text: The text to analyze
    
    Returns:
        bool: True if text contains too much boilerplate
    """
    boilerplate_patterns = [
        r'cookie[s]?\s+policy',
        r'privacy\s+policy',
        r'terms\s+of\s+service',
        r'subscribe|subscription',
        r'sign\s+up|login',
        r'advertisement',
        r'please\s+enable\s+javascript',
        r'this\s+site\s+uses\s+cookies',
        r'akzeptieren',
        r'datenschutz'
    ]
    
    # Count text segments
    segments = text.split('\n\n')
    content_segments = len(segments)
    
    pattern = '|'.join(boilerplate_patterns)
    matches = len(re.findall(pattern, text.lower()))
    text_length = len(text.split())
    
    # If a very short text has even one match, it's likely boilerplate
    if text_length < 150 and matches > 0:
        return True
    
    # If more than half the segments appear to be boilerplate, it's likely not useful
    if matches > content_segments / 2:
        return True
        
    # Otherwise, use a more balanced approach for longer content
    return matches > 5 or (matches > 2 and text_length < 300)



###################################################################################
def extract_with_readability_v2(html: str) -> Optional[str]:
    """
    Extract content and date using readability-lxml as fallback.
    
    Args:
        html: Raw HTML content
    
    Returns:
        extracted_text where it can be None
    """
    try:
        doc = readability.Document(html)
        readable_article = doc.summary()
                
        # Extract text
        h = HTML2Text()
        h.ignore_links = True
        h.ignore_images = True
        extracted_text = h.handle(readable_article)
        
        return extracted_text
    except Exception:
        return None





##############################################################################################
def make_request_with_retries(endpoint, params, headers, max_retries, timeout_duration):
    retry_count = 0
    while retry_count < max_retries:
        try:
            response = requests.get(endpoint, params=params, headers=headers, timeout=timeout_duration)
            # got something within the timeout time
            # on a later version we add features related to HTML errors
            resp_status = 'OK'
            return (response, resp_status)
        except Timeout:
            print(f"Request timed out. Attempt {retry_count + 1} of {max_retries}.")
        except RequestException as e:
            print(f"Request failed: {e}. Attempt {retry_count + 1} of {max_retries}.")
        retry_count += 1
    
    # maximum number of attempts reached
    print("Maximum retry attempts reached. Moving on.")
    return ('','Time out')



################################################
def parse_text_after_scraping_OLD(raw_html_content: str) -> Optional[str] :
    if not raw_html_content:
        return "Not available"

    ## Part I: get the paragraphs and similar structures from the html
    ## Note: I have tested trying to do both parse in one step, it leads to
    ## poor results (see Notebook "improving scraping" from January 2025)
    soup = BeautifulSoup(raw_html_content, 'html.parser')
    paragraphs = soup.find_all(["p", "div", "article", "main"])
    # bind it all together
    html_content = ''
    for para in paragraphs:
        html_content = html_content + str(para)

    ## Part II: clean up the html_content from typical "junk"
    # Boilerplate words to look for in short paragraphs
    BOILERPLATE_PATTERNS = ["cookie", "subscribe", "related articles", "advertising", 
                            "terms of service", "privacy policy", "author", "disclaimer"]
    # If a paragraph is shorter than this, we skip it (unless it passes certain checks)
    MIN_LENGTH = 30
    
    try:
        soup = BeautifulSoup(html_content, "html.parser")
        
        # Decompose noisy or layout tags
        for tag in soup.find_all([
            "script", "style", "iframe", "embed", "object", "noscript",
            "header", "footer", "nav", "aside", "form", "input", "button",
            "select", "textarea", "meta", "link", "figure", "canvas",
            "svg", "figcaption"
        ]):
            tag.decompose()
        
        # Decompose tags with undesired classes/IDs
        # Extend these if you find more patterns in your content
        NOISY_PATTERNS = [
            "ad", "banner", "sponsor", "promo", "commercial", "modal", "popup",
            "share", "social", "cookie", "accept", "subscribe", "login", "register",
            "notification", "breadcrumb", "pagination", "privacy", "terms", 
            "copyright", "disclaimer", "author", "byline", "date", "timestamp",
            "sidebar", "recommend", "related", "comment", "footer", "header",
            "contact", "about"
        ]
        
        NOISY_PATTERN = re.compile(r"(" + "|".join(NOISY_PATTERNS) + r")", re.I)
        
        for tag in soup.find_all(attrs={"class": NOISY_PATTERN}):
            tag.decompose()
        for tag in soup.find_all(attrs={"id": NOISY_PATTERN}):
            tag.decompose()
        
        # We will keep text mainly from <p>, <div>, <article>, <main> 
        # (you can add or remove tags depending on your data)
        candidate_tags = soup.find_all(["p", "div", "article", "main"])
        
        text_collected = []
        seen_texts = set()  # to avoid duplicates
        
        for elem in candidate_tags:
            text_content = elem.get_text(strip=True)
            
            # If it is empty, skip
            if not text_content:
                continue
            
            # If the text is too short, we suspect boilerplate or layout text
            if len(text_content) < MIN_LENGTH:
                # We allow it if it does not match typical boilerplate patterns
                if any(bp in text_content.lower() for bp in BOILERPLATE_PATTERNS):
                    continue

            # If we already captured this exact text, skip
            if text_content in seen_texts:
                continue
            
            text_collected.append(text_content)
            seen_texts.add(text_content)
        
        # Join all paragraphs, normalize whitespace, remove extraneous symbols
        final_text = " ".join(text_collected)
        final_text = re.sub(r"\s+", " ", final_text)
        final_text = re.sub(r"[©|\|•—]+", "", final_text)
        
        return final_text.strip() if final_text.strip() else None
    
    except Exception as e:
        print(f"Error parsing HTML: {e}")
        return None



def parse_text_after_scraping(raw_html_content: str) -> Optional[str]:
    """
    Extract meaningful content from raw HTML with improved job listing detection.
    
    Args:
        raw_html_content: Raw HTML content from webpage
        
    Returns:
        str: Extracted text content or "Not available" if extraction fails
    """
    if not raw_html_content:
        return "Not available"

    try:
        print("Trying to extract with BeautifulSoup")
        
        ## Part I: target job content specifically
        soup = BeautifulSoup(raw_html_content, 'html.parser')
        
        # Look specifically for job content containers first
        job_containers = soup.find_all(["div", "section", "article"], class_=lambda c: c and any(
            term in str(c).lower() for term in ["job", "position", "vacancy", "stellenangebot", "karriere"]))
        
        # If we found job containers, prioritize them
        if job_containers:
            html_content = ''
            for container in job_containers:
                html_content += str(container)
        else:
            # Otherwise fall back to regular paragraph extraction
            paragraphs = soup.find_all(["p", "div", "article", "main", "section"])
            html_content = ''
            for para in paragraphs:
                html_content += str(para)

        if not html_content:
            return "Not available"  # Guard against empty html_content

        ## Part II: clean up the html_content from typical "junk"
        # Boilerplate words to look for in short paragraphs
        BOILERPLATE_PATTERNS = ["cookie", "subscribe", "related articles", "advertising", 
                                "terms of service", "privacy policy", "author", "disclaimer"]
        # If a paragraph is shorter than this, we skip it (unless it passes certain checks)
        MIN_LENGTH = 30
        
        content_soup = BeautifulSoup(html_content, "html.parser")
        
        # Decompose noisy or layout tags
        for tag in content_soup.find_all([
            "script", "style", "iframe", "embed", "object", "noscript",
            "header", "footer", "nav", "aside", "form", "input", "button",
            "select", "textarea", "meta", "link", "figure", "canvas",
            "svg", "figcaption"
        ]):
            tag.decompose()
        
        # Decompose tags with undesired classes/IDs
        # Extend these if you find more patterns in your content
        NOISY_PATTERNS = [
            "ad", "banner", "sponsor", "promo", "commercial", "modal", "popup",
            "share", "social", "cookie", "accept", "subscribe", "login", "register",
            "notification", "breadcrumb", "pagination", "privacy", "terms", 
            "copyright", "disclaimer", "author", "byline", "date", "timestamp",
            "sidebar", "recommend", "related", "comment", "footer", "header",
            "contact", "about"
        ]
        
        NOISY_PATTERN = re.compile(r"(" + "|".join(NOISY_PATTERNS) + r")", re.I)
        
        for tag in content_soup.find_all(attrs={"class": NOISY_PATTERN}):
            tag.decompose()
        for tag in content_soup.find_all(attrs={"id": NOISY_PATTERN}):
            tag.decompose()
        
        # We will keep text mainly from <p>, <div>, <article>, <main> 
        # (you can add or remove tags depending on your data)
        candidate_tags = content_soup.find_all(["p", "div", "article", "main", "section", "h1", "h2", "h3", "h4", "ul", "li"])
        
        text_collected = []
        seen_texts = set()  # to avoid duplicates
        
        for elem in candidate_tags:
            text_content = elem.get_text(strip=True)
            
            # If it is empty, skip
            if not text_content:
                continue
            
            # If the text is too short, we suspect boilerplate or layout text
            if len(text_content) < MIN_LENGTH:
                # We allow it if it does not match typical boilerplate patterns
                if any(bp in text_content.lower() for bp in BOILERPLATE_PATTERNS):
                    continue
                # Also include shorter texts that might be job titles or important headers
                if elem.name in ["h1", "h2", "h3"] and len(text_content) > 10:
                    pass  # Keep important headers even if short
                else:
                    continue

            # If we already captured this exact text, skip
            if text_content in seen_texts:
                continue
            
            text_collected.append(text_content)
            seen_texts.add(text_content)
        
        # Join all paragraphs, normalize whitespace, remove extraneous symbols
        final_text = " ".join(text_collected)
        final_text = re.sub(r"\s+", " ", final_text)
        final_text = re.sub(r"[©|\|•—]+", "", final_text)
        
        # Add additional debugging to check output
        if final_text:
            print(f"Extracted text (100 chars): {final_text[0:100]}")
            return final_text.strip()
        else:
            return "Not available"
    
    except Exception as e:
        print(f"Error during extraction: {e}")
        return "Not available"