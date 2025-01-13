import google.generativeai as genai
import base64
import requests
import json
from PIL import Image, ImageDraw
import re
import numpy as np
import os
import pickle
import copy
import sys
import anthropic
import shutil
import keys
import time


###########################################

# API Keys
GOOGLE_API_KEY = keys.GOOGLE_API_KEY
claude_key = keys.claude_key

# Constants
CR_MODEL_NAME = "gemini-1.5-flash-002"
TYPES_OF_OCR = ['dom']
OCR_BREAKUP_NO = 4
WEIGHTS = {'tess': 0.2, 'opencv': 1, 'dom': 1}
FONTSIZE = 15



# Modify OCR types and weights
modified_types_of_ocr = []
weights_mod = {}
for to in TYPES_OF_OCR:
    ob = 1
    while ob <= OCR_BREAKUP_NO:
        modified_type = f"{to}_{ob}"
        modified_types_of_ocr.append(modified_type)
        weights_mod[modified_type] = WEIGHTS[to]
        ob += 1

#     return prompt
def resize_and_crop(input_path, output_path, x=None, y=None, padding=0):
    # Open the original image
    image = Image.open(input_path)
    original_width, original_height = image.size

    # Resize the image, maintaining the aspect ratio, with a max dimension of 951x1268 pixels
    max_width, max_height = 1092, 1092
    aspect_ratio = original_width / original_height

    if aspect_ratio > (max_width / max_height):
        new_width = min(max_width, original_width)
        new_height = int(new_width / aspect_ratio)
    else:
        new_height = min(max_height, original_height)
        new_width = int(new_height * aspect_ratio)

    resized_image = image.resize((new_width, new_height), Image.LANCZOS)

    # If no coordinates are provided, save the resized image and return
    if x is None or y is None:
        resized_image.save(output_path)
        return {
            'message': 'Image resized successfully',
            'original_width': original_width,
            'original_height': original_height,
            'new_width': new_width,
            'new_height': new_height
        }

    # Calculate padded bounding box
    left = max(0, x - padding)
    right = min(original_width, x + padding)
    top = max(0, y - padding)
    bottom = min(original_height, y + padding)

    # Ensure `right` is greater than `left` and `bottom` is greater than `top`
    if right <= left:
        right = left + 1
    if bottom <= top:
        bottom = top + 1

    # Ensure the crop is square by adjusting the smaller dimension
    width = right - left
    height = bottom - top

    if width != height:
        diff = abs(width - height) // 2
        if width < height:
            left = max(0, left - diff)
            right = min(original_width, right + diff)
            if right <= left:
                right = left + 1
        else:
            top = max(0, top - diff)
            bottom = min(original_height, bottom + diff)
            if bottom <= top:
                bottom = top + 1

    # Crop and resize if needed
    cropped_image = image.crop((left, top, right, bottom))
    cropped_width, cropped_height = cropped_image.size
    if cropped_width > max_width or cropped_height > max_height:
        resize_ratio = min(max_width / cropped_width, max_height / cropped_height)
        cropped_image = cropped_image.resize((int(cropped_width * resize_ratio), int(cropped_height * resize_ratio)), Image.LANCZOS)

    # Save the cropped image
    cropped_image.save(output_path)

    # Return details including bounding box
    return {
        'message': 'Image cropped and resized successfully',
        'original_width': original_width,
        'original_height': original_height,
        'new_width': cropped_image.width,
        'new_height': cropped_image.height,
        'bounding_box': {
            'left': left,
            'top': top,
            'right': right,
            'bottom': bottom
        }
    }




# def convert_coordinates(coordinates, conversion_info, bounding_box=None):
#     # bounding_box = {'left': 1, 'top': 2, 'right': 1000, 'bottom': 391}
#     # Extract conversion details
#     original_width = conversion_info['original_width']
#     original_height = conversion_info['original_height']
#     new_width = conversion_info['new_width']
#     new_height = conversion_info['new_height']

#     # If bounding box is provided, adjust the coordinates within the bounding box first
#     if bounding_box:
#         left = bounding_box['left']
#         top = bounding_box['top']
#         right = bounding_box['right']
#         bottom = bounding_box['bottom']

#         # Width and height of the bounding box
#         box_width = right - left
#         box_height = bottom - top

#         # Normalize the coordinates within the bounding box to get their relative position
#         x_within_box = coordinates['x'] / box_width
#         y_within_box = coordinates['y'] / box_height

#         # Map the coordinates to the new image dimensions
#         coordinates['x'] = left + x_within_box * box_width
#         coordinates['y'] = top + y_within_box * box_height

#     # Convert coordinates from new image back to original image
#     x_ratio =  original_width / new_width 
#     y_ratio = original_height / new_height


#     scaled_x = coordinates['x'] * x_ratio
#     scaled_y = coordinates['y'] * y_ratio

#     return {'x': scaled_x, 'y': scaled_y}

def get_action_and_candidate(payload, action_id, candidate_id):
    """
    Retrieve the action and the single candidate element from the payload by action_id and candidate_id.

    Args:
        payload (dict): The payload containing action tasks.
        action_id (int): The ID of the action to retrieve.
        candidate_id (int): The ID of the candidate to retrieve.

    Returns:
        dict: A dictionary containing the action and the single candidate element, or None if not found.
    """
    # Extract action tasks from the payload
    action_tasks = payload.get("action_tasks", [])
    
    # Find the action with the given action_id
    action = next((task for task in action_tasks if task.get("action_id") == action_id), None)
    if not action:
        return None

    # Find the single candidate with the specified candidate_id
    candidates = action.get("candidates", [])
    candidate = next((cand for cand in candidates if cand.get("candidate_id") == candidate_id), None)

    # If both action and candidate exist, return them
    if candidate:
        return {"action": action["description"], "candidate": candidate}
    
    return None


# Function to extract entities for evaluation
def extract_entities_for_evaluation(payload):
    extracted_data = {
        "visible_elements_from_instructions": payload.get("visible_elements_from_instructions"),
        "action_tasks": [
            {
                "action_id": action_task.get("action_id"),
                "description": action_task.get("description"),
                "candidates": [
                    {
                        "candidate_id": candidate.get("candidate_id"),
                        "element_description": candidate.get("element_description"),
                        "type_text": candidate.get("type_text"),
                        "keyboard_action": candidate.get("keyboard_action"),
                        "expected_outcome": candidate.get("expected_outcome"),
                        "coordinates": candidate.get("coordinates"), # coordinates_ready_to_act
                    }
                    for candidate in action_task.get("candidates", [])
                ],
            }
            for action_task in payload.get("action_tasks", [])
        ],
    }
    return extracted_data


def get_eval_prompt(workflow_memory, extra_instructions=None, site_wide_instructions=None, dimension_info=None,previous_step_detail=None,summary=None):
    prompt = f"""

You are part of a system that automates the exploration and documentation of web application workflows by analyzing UI states and interactions. Your role is to assist in navigating through product features by identifying and evaluating UI elements and their interactions, following standard user paths as designed in the product. Each workflow you analyze will be used to create customer support documentation, so you must prioritize generic, widely-applicable interactions that match the product's intended functionality, avoiding user-specific data or shortcuts. Your analysis should focus on actions that would be clear and repeatable in support documentation. When evaluating UI states and suggesting actions, consider how these steps would be documented for support agents and end users - they must follow standard navigation patterns and represent how the product is meant to be used. The goal is to build verified, standardized workflow guides that support agents can confidently share with customers. Don't use shortcuts or links available which don't appear to be perscriptive by web designers and seem temporary or a part of some recommendation system which could vary user by user.

Your task in particular, as a subsystem, is to evaluate the actions taken by the previous steps in the system.

    Instructions:

    Given:
    Images: Two or three screenshots of a webpage with width Image 1 representing the screenshot before last set of actions were taken, Image 2 containing the actions attempted described as blue dots overlayed over the first image, and Image 3 representing the screenshot after the last actions were taken.
    Evaluate: evaluate the success of each action and candidate, and provide advice for the next steps both 1) in terms of what other elements should have been hit and 2) describe a more percise location to click by analyzing the intended target, blue dot locations and coordinates used. The context of the evaluation is a site crawler trying to accomplish a workflow to gather product knowledge. Only the top ranked candidate actions will be attempted (where 'to_act' is True), but consider if alternate actions (where 'to_act' is False) would have been better and comment in the advice section.

    Crawl Instructions: {workflow_memory['workflow_instructions']}
    """

    if site_wide_instructions:
        prompt += f"\nHere is general info on the product your are evaluating: {site_wide_instructions}"

    if extra_instructions:
        prompt += f"\nAdditional instructions specific to this page: {extra_instructions}"

    if len(summary) > 0:

        prompt += f"""
        Summary of the crawl process so far:
        {summary}"""

    if len(previous_step_detail) > 0:

        prompt += f"""
        So far the steps taken and element info w/ coordinates and general descriptions are:
        {previous_step_detail}"""

    prompt += f"""  

    Evaluation Goals:
    1. **For Each Action and Candidate**:
    - Evaluate the success of each action.
    - Analyze if the candidate elements supported the action successfully.
    - Identify points of failure and explain why they occurred.
        * If the page shows "added to cart", then the goal has been completed
    2. **Advice for Next Steps**:
    - If the current state is acceptable:
        - Recommend the next logical step.
        - Provide advice on improving unsuccessful actions.
    - If the current state is not acceptable:
        - Recommend resetting to the last good step or to the initial state.
        - Provide advice on what to avoid or do differently in future steps.

    Output Format:

    Provide the evaluation in strict JSON format as follows (do not output anything other than the JSON object):
"""
    prompt+="""
    {
        "_expectations_analysis": string,  // Use previous actions expectations to determine if you are on the right track. However, the previous expectations are only a guess to help you determine if you're on the right track. Describe any discrepancies and why they might have occurred and why exactly they might have occured.
        "page_changed": boolean,  // Whether the pages changed after the last set of actions (compare Image 1 and Image 3). This is used to determine if we can simply retry at this same spot, or if the state changed and we have to start all over. Cosmetic changes or ad banner changes are fine, but any new expansions, drop downs, differnt pages, data entered, etc. should be considered a page change.
        "action_tasks": [  // Evaluate each action and its candidates.
            {
                "action_id": int,  // Unique ID of the action.
                "candidates": [  // Evaluate each candidate for the action.
                    {
                        "candidate_id": int,  // Unique ID of the candidate.
                        "success": boolean,  // Whether the candidate achieved it's purpose to led toward the desired goal.
                        "issues": string,  // Description of issues encountered, if any.
                        "_candidate_advice": string  // Specific advice for improving this candidate or action. Be detailed and provide actionable advice if someone is considering some similar type action task. Suggest using different candidates potentially.
                    }
                ]
                "_action_advice": string  // General advice for this action and its candidates. Try to select future candidates which might have a better chance.
            }
        ],
        
        "_expected_next_page_achieved": boolean,  // Whether the expected outcome of the crawl instructions was achieved from the previous action expectations (expected_outcome).
        "_precision_analysis": string,  // Analysis of the precision of the coordinates chosen for the element. Describe if the coordinates were off and how they could be improved.
        "_error_type": string,  // (choices: 'element','precision'). Whether the precision of the coordinates chosen for the element was off ('precision') or was the wrong element chosen ('element').
        "actions_succeeded": boolean,  // did the actions move forward toward the goal? true for yes, false for no.
        "_analysis_of_whole_process_progress": string,  // How well the process is going so far and what needs to be done next, if the entire crawl instructions have not been completed yet.
        "overall_goal_success": boolean,  // Whether the goal of the crawl process as a whole was successful and meeting the 'Crawl Instructions' 100% (True), or should it continue further (False).
        "summary": string  // Detailed summary of the whole process from start to finish for only the tasks in the previous 'summary' plus any successful tasks completed in the very previous step.
        "blue_dot_position": string, // Describe the position of the blue dot(s) in the image in relation to different page elements nearby.
        "target_element_position": string, // Describe the position of the target element(s) in the image in relation to different page elements nearby.
        "blue_dot_adjustment": string, // Describe how the blue dot(s) should be adjusted to better target the center(s) of intended element(s).
        "run_advice": string,  // If the actions didn't have an effect, or led to a wrong path where we would rather redo the entire process, provide advice on what should not have been done, or done better. Consider using different candidates, or not taking certain actions because of where they lead. Be detailed and thoughtful. Consider the learnings from previous advices and process summary to not suggest things that didn't work or to reinforce things that will likely work. Make this comprehensive advice. Advise also on impromvements in coordinates based on any errors in precision such mentioning the prevously used coordinates and how far of they were, or supplying suggested coordinates. Make sure to be detailed in exactly what went right and wrong from the start of the sequence, as well as other advice. The process might restart, might have limited context, and it needs to know what to do from the start and not just recent changes.
    }

    Using this format, evaluate the provided actions and candidates, and provide detailed advice to improve the workflow.
    """
    return prompt



def copy_and_rename_folder(folder_path, new_folder_name, rename_original_to=None):
    """
    Creates a copy of a folder with all its contents and optionally renames the original folder.
    Overwrites existing folders if they exist. Works with relative paths from current working directory.
    
    Args:
        folder_path (str): Path to the original folder (can be relative)
        new_folder_name (str): Name for the copied folder (just the name, not path)
        rename_original_to (str, optional): New name for the original folder (just the name, not path)
        
    Returns:
        tuple: (str, str) Paths to the new copy and original (possibly renamed) folder
    
    Raises:
        FileNotFoundError: If the original folder doesn't exist
    """
    # Convert relative path to absolute and get parent directory
    abs_original_path = os.path.abspath(folder_path)
    parent_dir = os.path.dirname(abs_original_path)
    
    if not os.path.exists(abs_original_path):
        raise FileNotFoundError(f"Original folder not found: {folder_path}")
    
    # Create path for the new copy in same directory as original
    new_path = os.path.join(parent_dir, new_folder_name)
    
    # Remove destination folder if it exists
    if os.path.exists(new_path):
        shutil.rmtree(new_path)
    
    # Copy the folder and its contents
    shutil.copytree(abs_original_path, new_path)
    
    # Handle renaming original folder
    final_original_path = abs_original_path
    if rename_original_to:
        renamed_path = os.path.join(parent_dir, rename_original_to)
        # Remove existing renamed folder if it exists
        if os.path.exists(renamed_path):
            shutil.rmtree(renamed_path)
        os.rename(abs_original_path, renamed_path)
        final_original_path = renamed_path
    
    # Convert back to relative paths for return values
    rel_new_path = os.path.relpath(new_path)
    rel_final_original = os.path.relpath(final_original_path)
    
    return rel_new_path, rel_final_original


# Function to copy and rename files
def copy_and_rename_file(old_path, new_path,delete_original=True):
    """
    Copies a file from the old path to the new path and then deletes the file at the old path.

    Args:
        old_path (str): The current path of the file.
        new_path (str): The new path where the file should be copied to.
    """
    # Check if source file exists
    if not os.path.isfile(old_path):
        print(f"Source file does not exist: {old_path}")
        return

    # Check if destination file already exists
    if os.path.isfile(new_path):
        print(f"Destination file already exists: {new_path} from {old_path}")
        return

    try:
        # Copy the file
        shutil.copy2(old_path, new_path)
        #print(f"File copied from {old_path} to {new_path}")

        # Delete the original file
        if delete_original:
            os.remove(old_path)
        #print(f"Original file deleted: {old_path}")
    except Exception as e:
        print(f"Error copying file: {e}")


def get_page_action_prompt(workflow_instructions, workflow_memory, extra_instructions=None, site_wide_instructions=None, dimension_info=None):
    
    dims = ''
    i = 1
    for c in dimension_info['chunks']:
        dims += f"Image: {i} has a width of {c['dimensions']['width']} and a height of {c['dimensions']['height']}\n"
        i += 1
    
    prompt = f"""

You are part of a system that automates the exploration and documentation of web application workflows by analyzing UI states and interactions. Your role is to assist in navigating through product features by identifying and evaluating UI elements and their interactions, following standard user paths as designed in the product. Each workflow you analyze will be used to create customer support documentation, so you must prioritize generic, widely-applicable interactions that match the product's intended functionality, avoiding user-specific data or shortcuts. Avoid also asking for help through search bars for functionality questions. Search and self-help processes can be used for other things other than functional support. Your analysis should focus on actions that would be clear and repeatable in support documentation. When evaluating UI states and suggesting actions, consider how these steps would be documented for support agents and end users - they must follow standard navigation patterns and represent how the product is meant to be used. The goal is to build verified, standardized workflow guides that support agents can confidently share with customers. Don't use shortcuts or links available which don't appear to be perscriptive by web designers and seem temporary or a part of some recommendation system which could vary user by user.

Your task in particular, as a subsystem, is to determine what action(s) to take next based on the goals given to you.

    Instructions:

    Given:
    Image: Given {len(dimension_info['chunks'])} screenshot(s) of a webpage with the following dimensions:
    {dims}

    -Your task is to analyze the next steps required to accomplish the given page action based ONLY on what you can observe in the screenshot, considering any prior action history. 
    -Behave like an expert test user and suggest appropriate actions to complete the page action. Make reasonable assumptions if needed. Try to suggest actions which are generalizable and don't pertain to a currently logged in user's data or product configuration. You will recieve screenshots after every action so you can see the results of your actions. 
    -Do not assume you know what the next state/page change will be and try to take actions with that assumpiton (like clicking dropdown items that may not be visible yet). 
    -Make use of dropdown arrows / chevrons / expandable sections to get as much information as possible. In those cases make sure you target such icons directly.
    -You will often need to complete forms (text fields, select from dropdown (arrows), etc.) and when doing so use realistic mock data for required fields only in order to traverse the pages.
    -If using the keyboard to cause an action vs. clicking, chose the keyboard, as it will lead to more precise actions (e.g. Enter to submit a form, Tab to move to the next field, etc.)

    IMPORTANT GUIDELINES FOR ORGANIZING ACTIONS:
    1. Each action_task represents ONE step in a sequence that must be performed in order
    2. Use separate action_tasks for steps that must happen sequentially (e.g., first type text, then submit search)
    3. Use candidates within an action_task for different ways to achieve the SAME action (e.g., clicking a button vs pressing Enter to submit)
    4. NEVER create separate action_tasks for things that are alternatives of each other - those should be candidates
    5. Each action_task should represent a distinct, necessary step in the workflow
    
    Examples of CORRECT organization:

    Correct example 1:
    - Action Task 1: Focus and Enter search text
      - Candidate 1: Click in main search box and type the text in
    - Action Task 2: Submit search
      - Candidate 1: Click search button
      - Candidate 2: Press Enter key

    Correct example 2:
    - Action Task 1: Click on the first product link (if visible)
     - Candidate 1: Click on the first product link
     - Candidate 2: Click on the second product link, which may or may not be present.
    
     #########################
    Example of INCORRECT organization:

    Incorrect example 1: 
    - Action Task 1: Open the category dropdown
      - Candidate 1: Click the category dropdown
    - Action Task 2: Select a category item from the dropdown  // Wrong! The dropdown item is likely not visible so you must take one action to open the dropdown and that's it. THe next iteration once you get a new screenshot will show you the dropdown items.
      - Candidate 1: Click the specific category item from the dropdown.

    Incorrect example 2: 
    - Action Task 1: Click search box
    - Action Task 2: Enter search text
    - Action Task 3: Click search button
    - Action Task 4: Press Enter key  // Wrong! Actions should be bundled and alternatives should be candidates
    
    Incorrect example 3: 
    - Action Task 1: Click on the "Products" link
    - Action Task 2: Click on the "Products Info" link // Wrong! Both actions are actually alternatives of the same action and should be candidates. Also, the first action would impact the visibility of the second action, so the second action should not happen.
    
    Page Action: {workflow_instructions}
    """

    if site_wide_instructions:
        prompt += f"\nHere is general info on the product your are evaluating: {site_wide_instructions}"

    if extra_instructions:
        prompt += f"\nAdditional instructions specific to this page: {extra_instructions}"

    prompt += """
    Output Format:

    Provide the results in JSON format according to the following schema:

    {
        "multiple_steps_required": boolean,
        "visible_elements_from_instructions": string,  // Describe which parts of the instruction set are visible in the screenshot.
        "summary_of_steps_so_far": string,  // Summary of previous actions to avoid repetition.
        "_advice_assessment": string,  // Assessment of the advice given in the previous step and how it might relate to this step.
        "_analysis_of_generilizability": string,  // Analysis if any candidate actions are not a part of the prescriptive web designer workflow, but rather temporary, non-generalizable to all user, or user-specific is some way. Write your analysis in a way to deter you from recommending such actions.
        "action_tasks": [  // Each task represents ONE step in a sequence. Multiple candidates within a task represent alternative ways to achieve that same step.
            {
                "description": "string",  // Description of this sequential step
                "candidates": [  // List of alternative ways to accomplish THIS SPECIFIC step
                    {
                        "element_description": "string",  // Detailed visual description of the element including location
                        "action": "string",  // Action type (Only: "click", "type", or "keyboard_action")
                        "type_text": "string",  // Text string to type if action is "type"
                        "expected_outcome": "string",  // Expected outcome after this specific action
                        "keyboard_action": "string",  // Keyboard action if applicable: "Enter", "Backspace", "Delete", "ArrowUp", "ArrowDown", "ArrowLeft", "ArrowRight", "Tab", "Escape"
                        "image_number": int,  // (1-"""+str(len(dimension_info['chunks']))+""") Represents the image number which best represents where the element is located (it could be represented in multiple screenshots, but pick the one where it's most visible)
                        "coordinates": {  // Location of the element within the given image (see image dimensions above for reference when creating coordinates)
                            "x": int,
                            "y": int
                        }
                    }
                ]
            }
        ],
        "error": "string",  // Error description if applicable
        "page_description": "string",  // General description of the page
        "expected_outcome_hopeful": "string"  // Expected outcome after performing all steps
    }

    Common Keyboard Actions:
    "Enter", "Backspace", "Delete", "ArrowUp", "ArrowDown", "ArrowLeft", "ArrowRight", "Tab", "Escape"
    """

    if workflow_memory:
        prompt += f"\nAction History (steps already taken which shouldn't be repeated): {workflow_memory}"

    return prompt




# def parse_json_response(response_text):
#     """
#     Parses a JSON-like string that might contain additional formatting, 
#     such as Markdown code blocks, extra newlines, or unexpected characters.
    
#     Args:
#         response_text (str): The raw JSON string output that might include formatting artifacts.

#     Returns:
#         dict: A cleaned and parsed dictionary representation of the JSON content.
#     """
#     try:
#         # Step 1: Clean the string to remove code blocks or unnecessary text
#         # Remove Markdown code block formatting (e.g., ```json\n and \n```)
#         cleaned_text = re.sub(r'```(?:json)?\n', '', response_text)
#         cleaned_text = cleaned_text.replace('```', '').strip()

#         # Step 2: Handle any stray characters or formatting issues
#         # Remove unwanted characters that may appear at the start/end of the string
#         cleaned_text = cleaned_text.strip('\'" \n')

#         # Step 3: Parse the cleaned string into a JSON dictionary
#         parsed_dict = json.loads(cleaned_text)
        
#         return parsed_dict
    
#     except json.JSONDecodeError as e:
#         print(response_text)

#         print(f"Error parsing JSON response: {e}")
#         return {"error": "Failed to parse the response"}
#     except Exception as e:
#         print(response_text)
#         print(f"Unexpected error during parsing: {e}")
#         return {"error": "Unexpected error occurred during parsing"}
import re
import json

def parse_json_response(response_text):
    """
    Parses a JSON-like string that might contain additional formatting, 
    such as Markdown code blocks, extra newlines, or unexpected characters.
    
    Additionally attempts to fix unescaped newlines in double-quoted sections.
    
    Returns:
        dict: A cleaned and parsed dictionary representation of the JSON content.
    """
    try:
        # Step 1: Remove ```json\n or ``` boundaries
        cleaned_text = re.sub(r'```(?:json)?\n?', '', response_text)
        cleaned_text = cleaned_text.replace('```', '').strip()

        # Step 2: Clean stray quotes or whitespace at the edges
        cleaned_text = cleaned_text.strip('\'" \n')

        # Step 3 (Optional): Attempt to fix unescaped newlines inside double quotes.
        # This is a naive approach: it looks for something like "some text\nsome text"
        # and converts the literal newline to \n. It's far from perfect,
        # but it may fix the typical multiline errors in JSON strings.
        def _escape_multiline_in_quotes(match):
            # group(1) = opening quote
            # group(2) = content of the string (possibly with newlines)
            # group(3) = closing quote
            # We replace real newlines in group(2) with \n
            content_fixed = match.group(2).replace('\n', '\\n').replace('\r', '\\n')
            return f'{match.group(1)}{content_fixed}{match.group(3)}'
        
        # Regex explanation:
        #   ("                - A literal double quote
        #   (?:\\.|[^"\\])*  - Any number of characters that are either escaped (\\.) 
        #                      or non-quote / non-backslash ([^"\\])
        #   )                - Capture that as group 2
        #   "                - A closing quote
        # We add the DOTALL/s to handle multiline
        cleaned_text = re.sub(
            r'(")((?:\\.|[^"\\])*)(")', 
            _escape_multiline_in_quotes, 
            cleaned_text, 
            flags=re.DOTALL
        )

        # Step 4: Finally parse into JSON
        parsed_dict = json.loads(cleaned_text)
        return parsed_dict

    except json.JSONDecodeError as e:
        print("Raw input:\n", response_text)
        print(f"Error parsing JSON response: {e}")
        return {"error": "Failed to parse the response"}
    except Exception as e:
        print("Raw input:\n", response_text)
        print(f"Unexpected error during parsing: {e}")
        return {"error": "Unexpected error occurred during parsing"}





genai.configure(api_key=GOOGLE_API_KEY)


def upload_to_gemini(path, mime_type=None):
    """Uploads the given file to Gemini."""
    file = genai.upload_file(path, mime_type=mime_type)
    #print(f"Uploaded file '{file.display_name}' as: {file.uri}")
    return file


# Generation configuration for Gemini models
generation_config = {
    "temperature": 0,
    "max_output_tokens": 8192,
    "response_mime_type": "application/json",
}

model = genai.GenerativeModel(
    model_name=CR_MODEL_NAME,
    generation_config=generation_config,
)

generation_config_unstruct = {
    "temperature": 0,
    "max_output_tokens": 8192,
}

model_unstruct = genai.GenerativeModel(
    model_name=CR_MODEL_NAME,
    generation_config=generation_config_unstruct,
)



def claude_run(screenshot_path, prompt,model,temperature=0.0):

    ###########################################


    client = anthropic.Anthropic(
        # defaults to os.environ.get("ANTHROPIC_API_KEY")
        api_key=claude_key,
    )

    # Create a list to store the encoded images
    decoded_images = []

    # Process each image in the images list
    i=1
    for image_path in screenshot_path:
        with open(image_path, "rb") as image_file:
            image_base64 = base64.b64encode(image_file.read()).decode('utf-8')

            decoded_images.append({
                    "type": "text",
                    "text": f"Image {i}:"
                })

            decoded_images.append({
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": "image/png",
                    "data": image_base64,
                },
            })
        i+=1

    # Prepare the message content
    message_content = decoded_images + [
        {
            "type": "text",
            "text": prompt
        }
    ]


    # Send the message to Claude
    message = client.messages.create(
        model=model,
        temperature=temperature,
        max_tokens=4024,
        messages=[
            {
                "role": "user",
                "content": message_content,
            }
        ],
    )

    return message.content[0].text#parse_json_response(message.content[0].text)

def analyze_page_actions(screenshot_path, prompt,api):
    """Analyzes the next steps required to accomplish the given page_action on a screenshot."""


    if api == "gemini":

        files = []
        for s in screenshot_path:
            files.append(upload_to_gemini(s, mime_type="image/png"))
        #print(files)

        send_to_generate = [prompt] + files

        #print(send_to_generate)
        response = model.generate_content(send_to_generate)

        response= response.text

    elif api == "claude":
        response = claude_run(screenshot_path, prompt = prompt,model="claude-3-5-sonnet-20241022")
    
    #print("LLM OUT:",response)
    response_json = parse_json_response(response)
    return response_json



# def get_faq_generate(prompt):
#     response = model_unstruct.generate_content([prompt])
    
#     return response.text


def dict_json(data=None, file_path=None, action="save"):
    """
    Saves a dictionary to a file or loads a dictionary from a file in JSON format.
    
    Args:
        data (dict, optional): The dictionary to save. Required for 'save' action.
        file_path (str): The file path where the dictionary should be saved/loaded.
        action (str): Action to perform - either "save" or "load". Default is "save".
    
    Returns:
        dict: Loaded dictionary if action is 'load', None if action is 'save'.
    """
    try:
        if action == "save":
            if data is None or file_path is None:
                raise ValueError("Data and file path must be provided for saving.")
            # Open the file in write mode and serialize the dictionary to JSON with UTF-8 encoding
            with open(file_path, 'w', encoding='utf-8') as file:
                json.dump(data, file, indent=4, ensure_ascii=False)
            #print(f"Dictionary saved successfully to {file_path}")
        
        elif action == "load":
            if file_path is None:
                raise ValueError("File path must be provided for loading.")
            
            # Open the file in binary mode first to check content
            with open(file_path, 'rb') as file:
                first_byte = file.read(1)
                # Check if the file is likely a text-based JSON file by inspecting the first byte
                if first_byte in [b'{', b'[']:
                    file.seek(0)
                    # Open the file again in text mode for JSON loading
                    with open(file_path, 'r', encoding='utf-8') as text_file:
                        data = json.load(text_file)
                    #print(f"Dictionary loaded successfully from {file_path}")
                    return data
                else:
                    raise ValueError("File does not appear to be a valid JSON file. It might be binary or another format.")

        else:
            raise ValueError("Action must be either 'save' or 'load'.")
    
    except (json.JSONDecodeError, ValueError, UnicodeDecodeError) as e:
        print(f"Error loading JSON file: {e}")
        return None




def save_or_load_pickle(filepath, data=None, mode='save'):
    """Saves or loads a dictionary to/from a pickle file.

    Args:
        filepath: The path to the pickle file.
        data: The dictionary to save (if mode is 'save').
        mode: 'save' to save the dictionary, 'load' to load it.

    Returns:
        The loaded dictionary if mode is 'load', otherwise None.
        Raises an exception if an error occurs during saving or loading.
    """
    if mode == 'save':
        if data is None:
            raise ValueError("Data must be provided when saving.")
        
        # Create directories only if there is a directory path
        directory = os.path.dirname(filepath)
        if directory:
            os.makedirs(directory, exist_ok=True)

        with open(filepath, 'wb') as f:
            pickle.dump(data, f)
        return None

    elif mode == 'load':
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"File not found: {filepath}")
        try:
            with open(filepath, 'rb') as f:
                loaded_data = pickle.load(f)
                return loaded_data
        except (pickle.UnpicklingError, EOFError) as e: # Handle potential pickle loading errors
            print(f"Error loading pickle file: {e}")
            raise Exception(f"Error loading pickle file: {e}") # Re-raise with a more informative message

    else:
        print(f"Invalid mode. Must be 'save' or 'load'.")
        raise ValueError("Invalid mode. Must be 'save' or 'load'.")






if sys.platform == "darwin":
    # It's a Mac
    print("Running on macOS")
    wdir_path = '/Users/dbosnjakovic/Desktop/python_projects/crawl'
    venv_folder = 'crawl/bin/python'
    curr_v = ''
elif sys.platform == "win32":
    # It's a Windows PC
    wdir_path = 'C:/Users/dusan/OneDrive/Desktop/pp/test/crawl'
    venv_folder = '.venv/Scripts/python.exe'
    curr_v = 'v6/'
    #print("Running on Windows")
else:
    print("Running on", sys.platform)



# Function to create folders
def create_folders(workflow_id, run_id):
    workflow_id = str(workflow_id)
    run_id = str(run_id)
    workflow_step_path = workflow_id + '/' + run_id
    os.makedirs(workflow_step_path, exist_ok=True)
    return workflow_step_path




def resize_browser_window(width: int, height: int) -> dict:
    response = requests.post(
        "http://127.0.0.1:8000/resize-window",
        params={"width": width, "height": height}
    )
    response.raise_for_status()
    return response.json()

# # Example usage
# if __name__ == "__main__":
#     # Replace with the actual base URL of your FastAPI server
#     base_url = "http://127.0.0.1:8000"
#     width = 1280
#     height = 720

#     result = resize_window_api(base_url, width, height)
#     print(result)




def evaluate_run_screenshots(workflow_memory, site_wide_instructions, run_rerun_path,dimension_info, previous_step_detail, summary, start_time=None):
    extra_instructions = ''
    action_prompt = get_eval_prompt(workflow_memory, extra_instructions=extra_instructions, site_wide_instructions=site_wide_instructions, dimension_info=dimension_info, previous_step_detail=previous_step_detail, summary=summary)
    eval_json = analyze_page_actions(screenshot_path=[f'{run_rerun_path}/chunks/resized_chunk_1.png', f'{run_rerun_path}/dots/resized_chunk_1.png', f'{run_rerun_path}/temp/resized_chunk_1.png'], prompt=action_prompt, api='claude')

    return eval_json


# Function to analyze raw screenshot
def analyze_raw_screenshot(workflow_memory, extra_instructions, site_wide_instructions, resized_image_paths, workflow_instructions, dimension_info, resize_screenshot_result_all_chunks,run_id,advice,summary):
    if len(advice)+len(summary) > 0:
        extra_instructions = f"{summary} /n{advice}"
        #print(f"Advice applied: {advice}")
    else:
        extra_instructions = ''
        #print("No advice applied")
        

    action_prompt = get_page_action_prompt(workflow_instructions, workflow_memory, extra_instructions=extra_instructions, site_wide_instructions=site_wide_instructions, dimension_info=dimension_info)

    #print(f"PROMPT for runID {run_id}: ",action_prompt)

    page_action_json_all = analyze_page_actions(screenshot_path=resized_image_paths, prompt=action_prompt, api='claude')

    try:
        page_action_json_ranked = filter_and_rank_outcome(page_action_json_all, dimension_info,resize_screenshot_result_all_chunks)
        return page_action_json_ranked
    except Exception as e:
        print(f"Error in filter_and_rank_outcome: {e}")
        return page_action_json_all

import requests

# ... other functions in helper.py ...

# helper.py
def filter_and_rank_outcome(data, dimension_info,resize_screenshot_result_all_chunks):
    modified_data = copy.deepcopy(data)
    modified_data['action_tasks'] = []
    ai = 0

    # Ratios for conversion
    # x_ratio = resize_screenshot_result_all_chunks['original_width'] / resize_screenshot_result_all_chunks['new_width']
    # y_ratio = resize_screenshot_result_all_chunks['original_height'] / resize_screenshot_result_all_chunks['new_height']

    for task in data['action_tasks']:
        for candidate in task['candidates']:
            if 'combined_score' not in candidate:
                candidate['combined_score'] = (
                    candidate.get('confidence', 0) * 0.5 +
                    candidate.get('generalizable', 0) * 0.5
                )

            # Convert coordinates to original image space
            if 'coordinates' in candidate and candidate['coordinates'] is not None:

                c_for_ratio = resize_screenshot_result_all_chunks[f'chunk_{candidate['image_number']}.png']
                print(c_for_ratio)
                x_ratio = c_for_ratio['original_width'] / c_for_ratio['new_width']
                y_ratio = c_for_ratio['original_height'] / c_for_ratio['new_height']
                print(x_ratio,y_ratio)

                add_height = 0
                for c in dimension_info['chunks']:
                    if c['chunk_number'] == candidate['image_number']:
                        add_height = c['coordinates']['top'] #* y_ratio
                        print(f"{c} was the right chunk")
                        break

                candidate['scroll_to']=add_height
                candidate['coordinates_ready_to_act'] = {
                    'x': candidate['coordinates']['x'] * x_ratio,
                    'y': candidate['coordinates']['y'] * y_ratio
                }
                candidate['coordinates_ready_to_draw'] = {
                    'x': candidate['coordinates']['x'] * x_ratio,
                    'y': candidate['coordinates']['y'] * y_ratio+add_height
                }

                print(f"Coordinates for action {ai} candidate: {candidate['coordinates_ready_to_act']} where previously {candidate['coordinates']} and we scrolled to {add_height}")

        sorted_candidates = sorted(task['candidates'], key=lambda x: x['combined_score'], reverse=True)
        for rank, candidate in enumerate(sorted_candidates, start=1):
            candidate['rank'] = rank
            candidate['to_act'] = rank == 1
            candidate['candidate_id'] = rank - 1

        modified_task = {
            'description': task['description'],
            'action_id': ai,
            'candidates': sorted_candidates
        }
        modified_data['action_tasks'].append(modified_task)
        ai += 1

    return modified_data



def send_action_request(payload, wait_time,run_rerun_path):
    """
    Sends a POST request to the FastAPI endpoint with the given payload and wait_time.

    :param payload: Dictionary containing the input payload.
    :param wait_time: Integer specifying the wait time between actions.
    :return: Response JSON from the API or an error message.
    """
    url = "http://127.0.0.1:8000/perform-actions"  # Update the URL if the endpoint runs on a different host/port

    try:
        response = requests.post(url, json=payload, params={"wait_time": wait_time, "run_rerun_path": run_rerun_path})
        response.raise_for_status()  # Raise an HTTPError if the response status is 4xx/5xx
        return response.json()
    except requests.RequestException as e:
        print(f"Error sending action request: {e}")
        return None

# helper.py
from PIL import Image, ImageDraw

# --- Helper functions for ipynb ---
def write_track_data(track_data, workflow_path):
    """Helper function to write tracking data to JSON file."""
    with open(f"{workflow_path}/tracking.json", "w") as f:
        json.dump(track_data, f, indent=4)



def draw_elements(page_action_json: dict, draw_dots: bool, diameter=20, introduce_wait=True):
    """
    Draws dots on the page for elements that will be acted upon.
    IMPORTANT: Expects coordinates in image space (e.g. 1058 x 1092)
    
    Args:
        page_action_json (dict): The JSON containing action tasks and candidates
        draw_dots (bool): Whether to draw dots on the page
        take_screenshot (bool): Whether to take a screenshot after drawing dots
        workflow_step_path (str): Path to save screenshots
        diameter (int): Diameter of dots to draw
        max_chunks (int): Maximum number of screenshot chunks
        resize_screenshot_result (dict): Contains original and new dimensions for coordinate conversion
    """
    #print("\nStarting draw_elements...")
    #print(f"Input page_action_json: {json.dumps(page_action_json, indent=2)}")
    

    duration = 3000  # Duration for drawing dots
    elements = []
    
    # Collect elements to mark with dots
    for task in page_action_json.get("action_tasks", []):
        candidates = task.get("candidates", [])
        for candidate in candidates:
            if candidate.get("to_act", False):
                coordinates_ready_to_draw = candidate.get("coordinates_ready_to_draw", {})  # Use original coordinates, NOT coordinates_ready_to_act
                if coordinates_ready_to_draw and coordinates_ready_to_draw.get("x") is not None and coordinates_ready_to_draw.get("y") is not None:
                    #print(f"Adding dot at coordinates: {coordinates_ready_to_act}")
                    elements.append({
                        "x": coordinates_ready_to_draw.get("x"),  # Keep in image space
                        "y": coordinates_ready_to_draw.get("y"),  # Keep in image space
                        "scroll_to": candidate.get("scroll_to"),
                        "action_id": task.get('action_id'),
                        "candidate_id": candidate.get('candidate_id')
                    })
    
    # Draw dots if enabled
    dot_response = None
    if draw_dots and elements:
        try:
            #print(f"Sending {len(elements)} elements to draw_dots endpoint")
            dot_response = requests.post(
                f"http://127.0.0.1:8000/draw_dots",
                params={"diameter": diameter,"duration":duration},
                json=elements,
                timeout=10
            )
            if dot_response.status_code != 200:
                print(f"Error drawing dots: {dot_response.json()}")
        except Exception as e:
            print(f"Exception during dot drawing: {e}")
    
    # Screenshot functionality is disabled but kept for reference
    screenshot_response = None
    #add time.sleep of duration ms
    if introduce_wait:
        time.sleep(duration/1000)
    
    return [], page_action_json, dot_response, screenshot_response


def create_highlighted_screenshot(run_id, run_data, workflow_step_path_temp, page_action_json_ranked, resize_screenshot_result, highlighted_images_dir):
    """
    Creates a highlighted screenshot based on the given bounding boxes.
    Uses element bounding boxes which are already in viewport space.
    
    Args:
        run_id (int): Current run ID
        run_data (dict): Data for the current run
        workflow_step_path_temp (str): Path to temporary workflow files
        page_action_json_ranked (dict): Action JSON containing tasks and candidates
        resize_screenshot_result (dict): Screenshot resize information
        highlighted_images_dir (str): Directory to save highlighted screenshots
    """
    #print("\nStarting highlight creation...")
    #print(f"Resize screenshot result: {resize_screenshot_result}")
    
    # Ensure directory exists
    os.makedirs(highlighted_images_dir, exist_ok=True)
    
    bounding_boxes = []
    for action_task in page_action_json_ranked.get("action_tasks", []):
        #print(f"\nProcessing action task: {action_task.get('description')}")
        
        # page_action_json_ranked['action_tasks'][0]['candidates'][0]['element_metadata']['boundingBox']

        for candidate in action_task.get("candidates", []):
            if candidate.get("to_act") and "element_metadata" in candidate:
                bbox = candidate["element_metadata"].get("boundingBox", {})
                #bbox = element_info.get("boundingBox")

                #response[0]['element_metadata']['boundingBox']

                
                if bbox:
                    #print(f"Found bounding box: {bbox}")

            
                    # print(f"Converting bounding box: {bbox}")
                    # x_ratio =  resize_screenshot_result['original_width'] / resize_screenshot_result['new_width']
                    # y_ratio = resize_screenshot_result['original_height'] / resize_screenshot_result['new_height']

                    # bbox['x'] = bbox['x'] * x_ratio
                    # bbox['y'] = bbox['y'] * y_ratio
                    # bbox['width'] = bbox['width'] * x_ratio
                    # bbox['height'] = bbox['height'] * y_ratio

                    
                    # print(f"Converted to bounding box: {bbox}")

                    bounding_boxes.append(bbox)  # Use as-is, already in viewport space
    
    if bounding_boxes:
        #print(f"\nDrawing {len(bounding_boxes)} bounding boxes")
        original_image_path = f"{workflow_step_path_temp}/chunk_1.png"
        highlighted_image_path = os.path.join(
            highlighted_images_dir,
            f"run_{run_id}_step_{len(run_data['steps']) if run_data and 'steps' in run_data else 0}_highlighted.png"
        )
        
        try:
            with Image.open(original_image_path) as img:
                draw = ImageDraw.Draw(img)
                for bbox in bounding_boxes:
                    # Draw rectangle around the element
                    shape = [
                        (bbox["x"] - 2, bbox["y"] - 2),
                        (bbox["x"] + bbox["width"] + 2, bbox["y"] + bbox["height"] + 2)
                    ]
                    draw.rectangle(shape, outline="red", width=3)
                img.save(highlighted_image_path)
                #print(f"Saved highlighted screenshot: {highlighted_image_path}")
        except Exception as e:
            print(f"Error creating highlighted image: {e}")
    else:
        print("No bounding boxes found to highlight")


def create_highlighted_screenshot_cairo(run_id, run_rerun_path, page_action_json_ranked, resize_screenshot_result):
    """
    Creates a highlighted screenshot based on the given bounding boxes using Cairo.
    Uses element bounding boxes which are already in viewport space.
    
    Args:
        run_id (int): Current run ID
        run_data (dict): Data for the current run
        workflow_step_path_temp (str): Path to temporary workflow files
        page_action_json_ranked (dict): Action JSON containing tasks and candidates
        resize_screenshot_result (dict): Screenshot resize information
        highlighted_images_dir (str): Directory to save highlighted screenshots
    """
    #print("\nStarting highlight creation...")
    #print(f"Resize screenshot result: {resize_screenshot_result}")
    
    
    bounding_boxes = []
    for action_task in page_action_json_ranked.get("action_tasks", []):
        #print(f"\nProcessing action task: {action_task.get('description')}")
        
        for candidate in action_task.get("candidates", []):
            if candidate.get("to_act") and "element_metadata" in candidate:
                bbox = candidate["element_metadata"].get("boundingBox", {})
                if bbox:
                    #print(f"Found bounding box: {bbox}")
                    bounding_boxes.append(bbox)  # Use as-is, already in viewport space
    
    if bounding_boxes:
        #print(f"\nDrawing {len(bounding_boxes)} bounding boxes")
        original_image_path = f"{run_rerun_path}/chunks/chunk_1.png"
        highlighted_image_path = f"{run_rerun_path}/highlights/chunk_1.png"
        
        # Use draw_with_cairo to create the highlighted image
        draw_with_cairo(original_image_path, highlighted_image_path, [], bounding_boxes) # Coordinates are not used for drawing, only bounding boxes
        #print(f"Saved highlighted screenshot: {highlighted_image_path}")
    else:
        print("No bounding boxes found to highlight")

# def perform_initial_setup(run_id, workflow_step_path, max_chunks=None):
#     """Performs initial setup for a run, including resizing and metadata gathering."""
#     print("Starting metadata gathering w/ window resizing")
#     start_time = time.time()
#     resize_browser_result = resize_browser_window(width=1252, height=1292)
#     url_metadata, screenshot_data = run_metadata_gather(
#         workflow_name=workflow_step_path, overlap_percentage=20, max_chunks=max_chunks
#     )
#     print(f"Finished gathering metadata with lap time: {time.time() - start_time}")

#     resize_screenshot_result = resize_and_crop(
#         input_path=f'{workflow_step_path}/chunk_1.png',
#         output_path=f'{workflow_step_path}/resized_orig.png'
#     )
#     copy_and_rename_file(f'{workflow_step_path}/resized_orig.png', f'{workflow_step_path}/resized.png')
#     print(f"Resized image with lap time: {time.time() - start_time}")

#     return resize_browser_result, url_metadata, screenshot_data



# ... (other functions in helper.py) ...

def perform_llm_analysis(workflow_memory, extra_instructions, site_wide_instructions, run_rerun_path, workflow_instructions, resize_screenshot_result_all_chunks,screenshot_data, run_id, start_time,advice,summary):
    """Performs LLM analysis to generate action plan."""
    #print("Starting vision analysis")


    resized_image_paths = []
    for c in resize_screenshot_result_all_chunks.keys():
        resized_image_path = f'{run_rerun_path}/chunks/resized_{c}'
        if not os.path.exists(resized_image_path): # Check if the resized image exists
            print(f"Error: Resized image not found at {resized_image_path}")
            return None  # Or handle the error appropriately
        else:
            resized_image_paths.append(resized_image_path)


    page_action_json_ranked = analyze_raw_screenshot(
        workflow_memory,
        extra_instructions,
        site_wide_instructions,
        resized_image_paths,
        workflow_instructions,
        dimension_info=screenshot_data,
        resize_screenshot_result_all_chunks = resize_screenshot_result_all_chunks,
        run_id=run_id,
        advice=advice,
        summary=summary
    )
    #print(f"Total candidates: {len(page_action_json_ranked.get('action_tasks', []))} with lap time: {time.time()-start_time}, about to perform actions")
    return page_action_json_ranked

import os

def get_files_with_extension(directory, extension):
    """
    Retrieves all filenames with a given extension in the specified directory.

    Args:
        directory (str): The path to the directory to search.
        extension (str): The file extension to filter by (e.g., ".txt").

    Returns:
        list: A list of filenames with the specified extension.
    """
    if not os.path.isdir(directory):
        raise ValueError(f"The path {directory} is not a valid directory.")

    # Ensure the extension starts with a dot
    if not extension.startswith("."):
        extension = "." + extension

    matching_files = []

    for root, _, files in os.walk(directory):
        for file in files:
            if file.endswith(extension):
                matching_files.append(file)

    return matching_files

# Example usage:
# directory_path = "/path/to/your/directory"
# file_extension = "txt"
# print(get_files_with_extension(directory_path, file_extension))


# Example usage:
# directory_path = "/path/to/your/directory"
# file_extension = "txt"
# print(get_files_with_extension(directory_path, file_extension))


def run_metadata_gather(output_path, overlap_percentage=20, max_chunks=None,wait_after_scroll=500):
    """
    Gather metadata and screenshots by calling the FastAPI server.

    :param workflow_name: Path to the directory where screenshots will be saved.
    :param overlap_percentage: Percentage of overlap between screenshot chunks.
    :param max_chunks: Maximum number of screenshot chunks to take.
    :return: A tuple containing dimension information and screenshot data.
    """
    try:
        # Call the server to extract metadata
        metadata_response = requests.get(f"http://127.0.0.1:8000/extract_metadata")
        if metadata_response.status_code != 200:
            raise Exception(f"Failed to fetch metadata. Status code: {metadata_response.status_code}. Message: {metadata_response}")
        url_metadata = metadata_response.json()

        # Call the server to take screenshots
        screenshot_response = requests.get(
            f"http://127.0.0.1:8000/screenshot",
            params={"output_path": output_path, "overlap_percentage": overlap_percentage,"max_chunks": max_chunks, "wait_after_scroll":wait_after_scroll,
                        "action_id": None,
                        "candidate_id": None
                    }
        )
        if screenshot_response.status_code != 200:
            raise Exception(f"Failed to take screenshots. Status code: {screenshot_response.status_code}")
        screenshot_data = screenshot_response.json()

        # Return metadata and screenshot information
        return url_metadata, screenshot_data

    except Exception as e:
        print(f"Error during metadata gather: {e}")
        raise

def reset_workflow(workflow_id, workflow_instructions, extra_instructions):
    workflow_memory = {}
    workflow_memory['workflow_id'] = workflow_id
    workflow_memory['workflow_instructions'] = workflow_instructions
    workflow_memory['previous_state_advice'] = ''
    workflow_memory['extra_instructions'] = extra_instructions
    workflow_memory['run_db'] = {}
    workflow_memory['summary'] = ''
    return workflow_memory

def add_step_to_run_data(run_data, step_type, details, data=None):
    """Adds a step to the run_data with the given type, details, and optional data."""
    step = {
        "step_type": step_type,
        "details": details,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
    }
    if data:
        step["data"] = data
    run_data["steps"].append(step)

def initialize_run_data(run_id, rerun_ct):
    """Initializes the run_data dictionary for a new run."""
    return {
        "run_id": run_id,
        "rerun_ct": rerun_ct,
        "start_time": time.strftime("%Y-%m-%d %H:%M:%S"),
        "steps": [],
    }


def handle_negative_evaluation(eval_json, workflow_memory, page_action_json_ranked):
    """Handles the case where the evaluation is negative (not overall_goal_success)."""
    advice = f"ADVICE FROM PREVIOUS STEPS OR RUNS: Consider this advice from previous attempts to guide you what to do next.: {eval_json['run_advice']}\n"
    summary = f"OVERALL PROCESS SUMMARY: Consider this summary from previous attempts to guide you what to do next.: {eval_json['summary']}\n"
    # if eval_json['can_continue']:
    #     for action_task in eval_json['action_tasks']:
    #         for candidate in action_task['candidates']:
    #             candidate_filtered = get_action_and_candidate(
    #                 page_action_json_ranked, action_id=action_task['action_id'], candidate_id=candidate['candidate_id']
    #             )
    #             if candidate_filtered:
    #                 if candidate['success']:
    #                     any_actions_succeeded = True
    #                 elif not candidate_filtered['candidate']['to_act']:
    #                     advice += f"- Suggestion: '{candidate_filtered['candidate']['element_description']}' was not acted upon previously. Advice: {candidate['advice']}\n"
    #                 elif candidate_filtered['candidate']['to_act']:
    #                     advice += f"- Failure: '{candidate_filtered['candidate']['element_description']}'. Advice: {candidate['advice']}\n"
    #             else:
    #                 advice += f"- General advice for action {action_task['action_id']}: {candidate['advice']}\n"
    # else:
    #     can_continue = False

    return advice, workflow_memory,summary


def setup_workflow_folders(workflow_id):
    """
    Creates and sets up all necessary folders for a workflow run.

    Args:
        workflow_id (str): ID of the workflow
        run_id (str/int): Current run number

    Returns:
        dict: Paths to all relevant folders
    """
    
    # Create base workflow path
    workflow_path = os.path.join(os.getcwd(), workflow_id)
    os.makedirs(workflow_path, exist_ok=True)
    
    # Find all numeric folders in the workflow path
    numeric_folders = [
        int(folder) for folder in os.listdir(workflow_path)
        if folder.isdigit() and os.path.isdir(os.path.join(workflow_path, folder))
    ]
    
    # Determine the next numeric folder name
    if numeric_folders:
        next_folder_number = max(numeric_folders) + 1
    else:
        next_folder_number = 0
    
    # Define the new numeric folder and its subfolders
    new_folder_path = os.path.join(workflow_path, str(next_folder_number))
    temp_path = os.path.join(new_folder_path, 'temp')
    dots_path = os.path.join(new_folder_path, 'dots')
    
    # Create the new folder and subfolders
    os.makedirs(temp_path, exist_ok=True)
    os.makedirs(dots_path, exist_ok=True)
    
    # Update workflow path to include the new numeric folder
    workflow_path = new_folder_path
    
    return {
        'next_folder_number': next_folder_number,
        'workflow_path': workflow_path,
        'temp_path': temp_path,
        'dots_path': dots_path,
    }

import os
import requests
from PIL import Image, ImageDraw
import json
import cairo

def test_coordinate_consistency(page_action_json_ranked, workflow_step_path, resize_screenshot_result):
    """
    Test coordinate consistency between clicking, element extraction, and visualization
    """
    results = []
    
    for task in page_action_json_ranked.get('action_tasks', []):
        for candidate in task.get('candidates', []):
            if candidate.get('to_act'):
                # Get the coordinates that would be used for clicking
                click_coords = candidate.get('coordinates_ready_to_act')
                if not click_coords:
                    continue
                
                # These are the coordinates we use for clicking and should be viewport coordinates
                viewport_x = click_coords['x']
                viewport_y = click_coords['y']
                
                results.append({
                    'description': candidate.get('element_description'),
                    'click_coordinates': {'x': viewport_x, 'y': viewport_y},
                })
                
                # Get element metadata using the SAME coordinates
                try:
                    metadata_response = requests.get(
                        'http://127.0.0.1:8000/extract_metadata',
                        params={'x': viewport_x, 'y': viewport_y}
                    )
                    
                    if metadata_response.status_code == 200:
                        metadata = metadata_response.json()
                        element_info = metadata.get('element_info', {})
                        bbox = element_info.get('boundingBox')
                        if bbox:
                            results[-1]['bounding_box'] = bbox
                except Exception as e:
                    print(f"Error fetching metadata: {e}")
                    results[-1]['metadata_error'] = str(e)

                # Test drawing a dot in browser at these coordinates
                try:
                    dot_response = requests.post(
                        'http://127.0.0.1:8000/draw_dots',
                        json=[{'x': viewport_x, 'y': viewport_y}]
                    )
                    results[-1]['dot_draw_result'] = dot_response.json()
                except Exception as e:
                    print(f"Error drawing dot: {e}")
                    results[-1]['dot_error'] = str(e)
                
    # Save results
    with open(os.path.join(workflow_step_path, 'coordinate_test_results.json'), 'w') as f:
        json.dump(results, f, indent=2)
    
    return results

def draw_with_cairo(image_path, output_path, coordinates, bounding_boxes):
    """
    Draw visualization using Cairo with improved glowing effect
    """
    # print("\nDebug - Drawing inputs:")
    # print(f"Image path: {image_path}")
    # print(f"Output path: {output_path}")
    # print(f"Bounding boxes: {bounding_boxes}")
    
    # Load original image and convert to RGBA
    with Image.open(image_path) as img:
        img = img.convert('RGBA')
        width, height = img.size
        
        # Convert PIL image to a format Cairo can use
        img_data = bytearray(img.tobytes('raw', 'BGRa'))
    
    # Create the base surface and paint the background image
    surface = cairo.ImageSurface.create_for_data(
        img_data, cairo.FORMAT_ARGB32, width, height, width * 4)
    ctx = cairo.Context(surface)
    
    # Draw bounding boxes with radial gradient glow
    for bbox in bounding_boxes:
        x = bbox['x']
        y = bbox['y']
        w = bbox['width']
        h = bbox['height']
        
        # Calculate center and radius for radial gradient
        center_x = x + w/2
        center_y = y + h/2
        radius = max(w/2, h/2) + 10  # Add some padding
        
        # Create radial gradient for glow effect
        gradient = cairo.RadialGradient(
            center_x, center_y, radius - 10,  # Inner circle
            center_x, center_y, radius        # Outer circle
        )
        
        # Add multiple color stops for smoother gradient
        gradient.add_color_stop_rgba(0, 0.2, 0.8, 0.8, 0.3)  # Inner teal
        gradient.add_color_stop_rgba(0.7, 0.2, 0.8, 0.8, 0.1)  # Mid teal
        gradient.add_color_stop_rgba(1, 0.2, 0.8, 0.8, 0)    # Transparent edge
        
        # Draw rectangle with gradient
        ctx.set_source(gradient)
        ctx.set_line_width(2)
        
        # Draw multiple rectangles with decreasing opacity for glow
        for i in range(5):
            padding = i * 2
            ctx.rectangle(
                x - padding,
                y - padding,
                w + (padding * 2),
                h + (padding * 2)
            )
            ctx.stroke()
    
    # Save result
    try:
        surface.write_to_png(output_path)
        #print(f"Successfully saved Cairo visualization to: {output_path}")
    except Exception as e:
        print(f"Error saving Cairo visualization: {e}")
        raise
    
    return True

def test_visualization(workflow_step_path, page_action_json_ranked, resize_screenshot_result):
    """
    Test the complete visualization process
    """
    # First run coordinate consistency test
    test_results = test_coordinate_consistency(
        page_action_json_ranked, 
        workflow_step_path,
        resize_screenshot_result
    )
    
    # Get original screenshot path (unresized)
    original_image_path = os.path.join(workflow_step_path, 'chunk_1.png')
    
    # Prepare coordinates and bounding boxes from test results
    coordinates = []
    bounding_boxes = []
    
    for result in test_results:
        if 'click_coordinates' in result:
            coordinates.append(result['click_coordinates'])
        if 'bounding_box' in result:
            bounding_boxes.append(result['bounding_box'])
    
    # Create visualization using Cairo
    output_path = os.path.join(workflow_step_path, 'cairo_visualization.png')
    draw_with_cairo(original_image_path, output_path, coordinates, bounding_boxes)
    
    return {
        'test_results': test_results,
        'visualization_path': output_path
    }

def navigate_to_url_from_metadata(url_metadata):
    """
    Navigates to a specific URL using the /navigate FastAPI endpoint.

    Args:
        url_metadata: The URL metadata dictionary.
    """
    navigation_payload = {
        "status": "success",  # Assuming success for the structure
        "url_metadata": url_metadata,
        "dimensions": {}  # You can populate dimensions if needed
    }

    try:
        response = requests.post("http://127.0.0.1:8000/navigate", json=navigation_payload)
        response.raise_for_status()  # Raise an exception for bad status codes
        #print(response.json())
    except requests.exceptions.RequestException as e:
        print(f"Error during navigation: {e}")