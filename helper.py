#import google.generativeai as genai
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
from anthropic import Anthropic
from log_config import get_logger

logger = get_logger(__name__)  # Use module name for easier identification




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


import copy
import math

# Function to calculate the area of a rectangle given it's dimensions (height and width) and the number of tokens
# that can be used to describe the image. The area of the rectangle should be greater than or equal to the number of tokens.
def largest_height_given_width(max_tokens,orig_width,suggested_height=None):
    """
    Returns the smallest integer dimensions (height, width) that preserve
    the original aspect ratio and ensure:
        (new_width * new_height) >= 1,200,000

    If the original image is already >= 1,200,000 in area, returns the
    original dimensions unchanged.

    """
    not_found = True
    adjusted_width = copy.deepcopy(orig_width)
    if suggested_height:
        adjusted_height = suggested_height
    else:
        adjusted_height = copy.deepcopy(orig_width)



    while not_found:

        test_tokens = adjusted_height * adjusted_width / 750

        adjusted_height_down = adjusted_height - 1
        adjusted_height_up = adjusted_height + 1

        test_tokens_up = adjusted_height_up * adjusted_width / 750

        if test_tokens_up < max_tokens:
            adjusted_height = adjusted_height_up
        elif test_tokens< max_tokens:
            not_found = False
        else:
            adjusted_height = adjusted_height_down




    
    return adjusted_height, test_tokens

def smallest_dimensions_meeting_area(orig_height, orig_width):
    """
    Returns the smallest integer dimensions (height, width) that preserve
    the original aspect ratio and ensure:
        (new_width * new_height) >= 1,200,000

    If the original image is already >= 1,200,000 in area, returns the
    original dimensions unchanged.

    """
    not_found = True
    adjusted_height = copy.deepcopy(orig_height)
    adjusted_width = copy.deepcopy(orig_width)

    aspect_ratio = adjusted_height / adjusted_width
    tokens = 0

    while not_found:

        tokens = adjusted_height * adjusted_width / 750

        if tokens < 1600:
            not_found = False
        else:
            adjusted_height = adjusted_height - 1
            # round down adjusted width after maintaining aspect ratio
            adjusted_width = math.floor(adjusted_height / aspect_ratio)


    
    return adjusted_height, adjusted_width,tokens,aspect_ratio


#     return prompt
def resize_and_crop(input_path, output_path, x=None, y=None, padding=0):
    max_width, max_height = 1092, 1092 # for cropping only
    # Open the original image
    image = Image.open(input_path)
    original_width, original_height = image.size
    #print(original_height, original_width)

    new_height, new_width,tokens,aspect_ratio = smallest_dimensions_meeting_area(original_height, original_width)


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
                        "_need_to_click_dropdown_arrow":candidate.get("_need_to_click_dropdown_arrow"),
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


def get_eval_prompt(workflow_instructions, extra_instructions=None, site_wide_instructions=None,site_description=None, dimension_info=None,previous_step_detail=None,summary=None):
    prompt = f"""

You are part of a system that automates the exploration and documentation of web application workflows by analyzing UI states and interactions. Your role is to assist in navigating through product features by identifying and evaluating UI elements and their interactions, following standard user paths as designed in the product. Each workflow you analyze will be used to create customer support documentation, so you must prioritize generic, widely-applicable interactions that match the product's intended functionality, avoiding user-specific data or shortcuts. Your analysis should focus on actions that would be clear and repeatable in support documentation. When evaluating UI states and suggesting actions, consider how these steps would be documented for support agents and end users - they must follow standard navigation patterns and represent how the product is meant to be used. The goal is to build verified, standardized workflow guides that support agents can confidently share with customers. Don't use shortcuts or links available which don't appear to be perscriptive by web designers and seem temporary or a part of some recommendation system which could vary user by user.

Your task in particular, as a subsystem, is to evaluate the actions taken by the previous steps in the system.

    Instructions:

    Given:
    Images: Two or three screenshots of a webpage with width Image 1 representing the screenshot before last set of actions were taken, Image 2 containing the actions attempted described as blue dots overlayed over the first image, and Image 3 representing the screenshot after the last actions were taken.
    Evaluate: evaluate the success of each action and candidate, and provide advice for the next steps both 1) in terms of what other elements should have been hit and 2) describe a more percise location to click by analyzing the intended target, blue dot locations and coordinates used. The context of the evaluation is a site crawler trying to accomplish a workflow to gather product knowledge. Only the top ranked candidate actions will be attempted (where 'to_act' is True), but consider if alternate actions (where 'to_act' is False) would have been better and comment in the advice section.

    Crawl Instructions: {workflow_instructions}
    """

    if site_description:
        prompt += f"\nHere is the website you are on: {site_description}"
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
        logger.error(f"Source file does not exist: {old_path}")
        return

    # Check if destination file already exists
    if os.path.isfile(new_path):
        logger.warning(f"Destination file already exists: {new_path}")
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
        logger.error(f"Error copying file: {e}")


def get_page_action_prompt(workflow_instructions, extra_instructions=None, site_wide_instructions=None,site_description = None, best_image=None,summary = None,advice = None,last_rerun_advice = None):
    
    dims = f"Image: has a width of {best_image['resized_dimensions']['width']} and a height of {best_image['resized_dimensions']['height']}\n"
    
    prompt = f"""

You are part of a system that automates the exploration and documentation of web application workflows by analyzing UI states and interactions. Your role is to assist in navigating through product features by identifying and evaluating UI elements and their interactions, following standard user paths as designed in the product. Each workflow you analyze will be used to create customer support documentation, so you must prioritize generic, widely-applicable interactions that match the product's intended functionality, avoiding user-specific data or shortcuts. Avoid also asking for help through search bars for functionality questions. Search and self-help processes can be used for other things other than functional support. Your analysis should focus on actions that would be clear and repeatable in support documentation. When evaluating UI states and suggesting actions, consider how these steps would be documented for support agents and end users - they must follow standard navigation patterns and represent how the product is meant to be used. The goal is to build verified, standardized workflow guides that support agents can confidently share with customers. Don't use shortcuts or links available which don't appear to be perscriptive by web designers and seem temporary or a part of some recommendation system which could vary user by user.

Your task in particular, as a subsystem, is to determine what action(s) to take next based on the goals given to you.

    Instructions:

    Given:
    Image: Given the screenshot of a webpage with the following dimensions. Use this information when calculating the cooringates of elements on the image.

    {dims}

    -Your task is to analyze the next step required to accomplish the given page action based ONLY on what you can observe in the screenshot, considering any prior action history. 
    -After each step (consisting of possibly multiple actions) a verification phase will commence. So, a step should not take actions which change the state of the page without first verifying the outcome of the actions taken (e.g. submitting a form without first verifying the form fields are correct).
    -Behave like an expert test user and suggest appropriate actions to complete the page action. Make reasonable assumptions if needed. Try to suggest actions which are generalizable and don't pertain to a currently logged in user's data or product configuration. You will recieve screenshots after every action so you can see the results of your actions. 
    -Do not assume you know what the next state/page change will be and try to take actions with that assumpiton (like clicking dropdown items that may not be visible yet). After exploring dropdown options, separate selecting an option from opening the dropdown as the next step.
    -You will often need to complete forms (text fields, select from dropdown (arrows), etc.) and when doing so use realistic mock data for required fields only in order to traverse the pages. IMPORTANT: only focus on required fields to save time and avoid unnecessary actions.
    -If using the keyboard to cause an action vs. clicking, chose the keyboard, as it will lead to more precise actions (e.g. Enter to submit a form, Tab to move to the next field, etc.)
    -Make use of dropdown arrows / chevrons / expandable sections to get as much information as possible. In those cases make sure you target such icons directly.
    -If the forms have dropdowns you must click the dropdown arrows to see the options and then select an option. Don't begin entering text into a dropdown field without first clicking the dropdown arrow.
    -You should try to make sure that you confirm the effects of your actions before taking further actions which change state. For exmple, when completing a form make sure the form fields are all entered correctly before submitting the form.
    -Interact with all form elements in order to create documentation about them.

    IMPORTANT GUIDELINES FOR ORGANIZING ACTIONS:
    1. Each action_task represents ONE step in a sequence that must be performed in order
    2. Use separate action_tasks for steps that must happen sequentially (e.g., enter form fields in sequence, but submit as a separate step.)
    3. Use candidates within an action_task for different ways to achieve the SAME action (e.g., clicking a button vs pressing Enter to submit)
    4. NEVER create separate action_tasks for things that are alternatives of each other - those should be candidates
    5. Each action_task should represent a distinct, necessary step in the workflow
    6. If an action changes state or leads to a new page, it should be a separate step in order to first verify the outcome before proceeding.
    
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

    if site_description:
        prompt += f"\nHere is the website your are evaluating: {site_description}"
    if site_wide_instructions:
        prompt += f"\nHere is general info on the product your are evaluating: {site_wide_instructions}"

    if extra_instructions:
        prompt += f"\nAdditional instructions specific to this page or action summary of the workflow so far: {extra_instructions}"

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
                        "image_description":"string",  // Detailed description of the image where the image is located
                        "_need_to_click_dropdown_arrow":boolean, //if the element has a dropdown arrow or indicator then select True and suggest to click on that part of the element elsewhere.
                        "element_description": "string",  // Detailed visual description of the element and must also include description of location of the element relative to the image boundaries and compared with other elements within the screenshot
                        "action": "string",  // Action type (Only: "click", "type", or "keyboard_action")
                        "type_text": "string",  // Text string to type if action is "type"
                        "expected_outcome": "string",  // Expected outcome after this specific action
                        "keyboard_action": "string",  // Keyboard action if applicable: "Enter", "Backspace", "Delete", "ArrowUp", "ArrowDown", "ArrowLeft", "ArrowRight", "Tab", "Escape"
                        "coordinates": {  // Location of the element within the given image (see image dimensions above for reference when creating coordinates).
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

    if len(summary) > 0:
        prompt += f"\nAction History (steps already taken which shouldn't be repeated): {summary}\n\n"

    if len(advice) > 0:
        prompt += advice

    if len(last_rerun_advice)>0:
        prompt += "Use this advice from any failed previous attempts to complete this entire workflow. It may not relate to this step, but consider it non the less: "+last_rerun_advice

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
import re
import json
import logging

logger = logging.getLogger(__name__)

import re
import json
import logging

logger = logging.getLogger(__name__)


import re
import json
import logging

logger = logging.getLogger(__name__)


import re
import json
import logging

logger = logging.getLogger(__name__)


import re
import json
import logging

logger = logging.getLogger(__name__)


import re
import json
import logging

logger = logging.getLogger(__name__)



# def parse_json_response(response_text):
#     """
#     Parses a JSON-like string that might contain additional formatting such as log messages,
#     Markdown code blocks, extra newlines, or unexpected characters.
    
#     It first attempts to extract JSON content from a markdown code block delimited by 
#     ```json and ```. If that fails, it falls back to extracting the JSON between 
#     the first '{' and the last '}'.
    
#     Additionally, it attempts to fix unescaped newlines in double-quoted sections.
    
#     Returns:
#         dict: A cleaned and parsed dictionary representation of the JSON content.
#     """
#     try:
#         cleaned_text = None
#         start_marker = "```json"
#         end_marker = "```"

#         # Step 1: Extract JSON using string partitioning.
#         if start_marker in response_text:
#             # Partition the string at the start_marker.
#             _, _, remainder = response_text.partition(start_marker)
#             # Remove any leading whitespace/newlines.
#             remainder = remainder.lstrip()
#             # Partition the remainder at the end_marker.
#             json_content, _, _ = remainder.partition(end_marker)
#             cleaned_text = json_content.strip()
#         else:
#             # Fallback: extract JSON between the first '{' and the last '}'.
#             first_brace = response_text.find('{')
#             last_brace = response_text.rfind('}')
#             if first_brace != -1 and last_brace != -1:
#                 cleaned_text = response_text[first_brace:last_brace + 1].strip()
#             else:
#                 raise ValueError("No JSON object found in the response.")

#         # Step 2: Fix unescaped newlines within double quotes.
#         def _escape_multiline_in_quotes(match):
#             content_fixed = match.group(2).replace('\n', '\\n').replace('\r', '\\n')
#             return f'{match.group(1)}{content_fixed}{match.group(3)}'
        
#         cleaned_text = re.sub(
#             r'(")((?:\\.|[^"\\])*)(")',
#             _escape_multiline_in_quotes,
#             cleaned_text,
#             flags=re.DOTALL
#         )

#         # Step 3: Parse the cleaned text into a JSON object.
#         parsed_dict = json.loads(cleaned_text)
#         return parsed_dict

#     except json.JSONDecodeError as e:
#         logger.error(f"Error parsing JSON response: {e}. LLM API response is {response_text}")
#         return {"error": "Failed to parse the response"}
#     except Exception as e:
#         logger.error(f"Unexpected error during parsing: {e}. LLM API response is {response_text}")
#         return {"error": "Failed to parse the response"}



def parse_json_response(response_text):
    """
    Parses a JSON-like string that might contain additional formatting such as log messages,
    Markdown code blocks, extra newlines, or unexpected characters.
    
    It first attempts to extract JSON content from a markdown code block delimited by 
    ```json and ```. If that fails, it falls back to extracting the JSON between 
    the first '{' and the last '}'.
    
    Additionally, it attempts to fix unescaped newlines in double-quoted sections.
    
    Returns:
        dict: A cleaned and parsed dictionary representation of the JSON content.
    """
    try:
        cleaned_text = None
        start_marker = "```json"
        end_marker = "```"

        # Step 1: Extract JSON using string partitioning.
        if start_marker in response_text:
            # Partition the string at the start_marker.
            _, _, remainder = response_text.partition(start_marker)
            # Remove any leading whitespace/newlines.
            remainder = remainder.lstrip()
            # Partition the remainder at the end_marker.
            json_content, _, _ = remainder.partition(end_marker)
            cleaned_text = json_content.strip()
        else:
            # Fallback: extract JSON between the first '{' and the last '}'.
            first_brace = response_text.find('{')
            last_brace = response_text.rfind('}')
            if first_brace != -1 and last_brace != -1:
                cleaned_text = response_text[first_brace:last_brace + 1].strip()
            else:
                raise ValueError("No JSON object found in the response.")

        # Step 2: Fix unescaped newlines within double quotes.
        def _escape_multiline_in_quotes(match):
            content_fixed = match.group(2).replace('\n', '\\n').replace('\r', '\\n')
            return f'{match.group(1)}{content_fixed}{match.group(3)}'
        
        cleaned_text = re.sub(
            r'(")((?:\\.|[^"\\])*)(")',
            _escape_multiline_in_quotes,
            cleaned_text,
            flags=re.DOTALL
        )

        # Step 3: Parse the cleaned text into a JSON object.
        parsed_dict = json.loads(cleaned_text)
        return parsed_dict

    except json.JSONDecodeError as e:
        logger.error(f"Error parsing JSON response: {e}. LLM API response is {response_text}")
        return {"error": "Failed to parse the response"}
    except Exception as e:
        logger.error(f"Unexpected error during parsing: {e}. LLM API response is {response_text}")
        return {"error": "Failed to parse the response"}





#genai.configure(api_key=GOOGLE_API_KEY)


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

# model = genai.GenerativeModel(
#     model_name=CR_MODEL_NAME,
#     generation_config=generation_config,
# )

generation_config_unstruct = {
    "temperature": 0,
    "max_output_tokens": 8192,
}

# model_unstruct = genai.GenerativeModel(
#     model_name=CR_MODEL_NAME,
#     generation_config=generation_config_unstruct,
# )


from concurrent.futures import ThreadPoolExecutor
import concurrent.futures
from anthropic import Anthropic

def claude_run(screenshot_path, prompt, model, temperature=0.0):
    def _run_claude():
        try:
            client = anthropic.Anthropic(api_key=claude_key)
            
            # Create a list to store the encoded images
            decoded_images = []

            # Process each image in the images list
            logger.info(f"Processing {len(screenshot_path)} images")
            i=1
            for image_path in screenshot_path:
                logger.info(f"Processing image {image_path} ~{os.path.getsize(image_path)/1000}KB")
                if os.path.getsize(image_path)> 1000000: # 
                    logger.error(f"Image {image_path} is ~{os.path.getsize(image_path)/1000}KB. It is too large to process.")
                else:




                    try:
                        ensure_writable_file_path(image_path)
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
                    except Exception as e:
                        raise Exception(f"Error accessing or processing image {image_path}: {str(e)}")

            logger.info(f"Finished processing images")
            # Prepare the message content
            message_content = decoded_images + [
                {
                    "type": "text",
                    "text": prompt
                }
            ]
            logger.info(f"Begining Claude LLM API call with {len(message_content)} message parths and {len(prompt)} characters in prompt")
            # Send the message to Claude
            try:
                message = client.messages.create(
                    model=model,
                    temperature=temperature,
                    max_tokens=8192,
                    messages=[
                        {
                            "role": "user",
                            "content": message_content,
                        }
                    ],
                )
                logger.info(f"Claude LLM API call completed")
            except Exception as e:
                raise Exception(f"Claude API error: {str(e)}")

            return message.content[0].text, message

        except Exception as e:
            if "api" in str(e).lower():
                raise Exception(f"Anthropic API error: {str(e)}")
            else:
                raise Exception(f"Unexpected error: {str(e)}")

    # Run with timeout
    with ThreadPoolExecutor() as executor:
        future = executor.submit(_run_claude)
        try:
            return future.result(timeout=60)  # 30 seconds timeout
        except concurrent.futures.TimeoutError:
            raise Exception("Request timed out after 30 seconds")
        except Exception as e:
            raise e

def analyze_page_actions(screenshot_path, prompt,api):
    """Analyzes the next steps required to accomplish the given page_action on a screenshot."""
    raw = None

    response_text = None


    if api == "gemini":

        files = []
        for s in screenshot_path:
            files.append(upload_to_gemini(s, mime_type="image/png"))
        #print(files)

        send_to_generate = [prompt] + files

        #print(send_to_generate)
        raw = model.generate_content(send_to_generate)

        response_text= raw.text

    elif api == "claude":
        
        logger.info(f"Sending to Claude LLM API")


        try:
            #response_text,raw = claude_run(screenshot_path, prompt = prompt,model="claude-3-5-sonnet-20241022")
            response_text,raw = claude_run(screenshot_path, prompt = prompt,model="claude-3-7-sonnet-20250219")
            logger.info(f"Completed Claude LLM API call")
        except Exception as e:
            print(f"Error occurred during Claude run: {str(e)}")
            logger.error(f"Error occurred during Claude run: {str(e)}")
            logger.info(f"Raw response: {str(raw)}")
        
    
    #print("LLM OUT:",response)
    try:
        response_json = parse_json_response(response_text)
    except Exception as e:
        print(f"Error occured during parsing: {str(e)}")

    return response_json,raw



# def get_faq_generate(prompt):
#     response = model_unstruct.generate_content([prompt])
    
#     return response.text


# def dict_json(data=None, file_path=None, action="save"):
#     """
#     Saves a dictionary to a file or loads a dictionary from a file in JSON format.
    
#     Args:
#         data (dict, optional): The dictionary to save. Required for 'save' action.
#         file_path (str): The file path where the dictionary should be saved/loaded.
#         action (str): Action to perform - either "save" or "load". Default is "save".
    
#     Returns:
#         dict: Loaded dictionary if action is 'load', None if action is 'save'.
#     """
#     try:
#         if action == "save":
#             if data is None or file_path is None:
#                 raise ValueError("Data and file path must be provided for saving.")
#             # Open the file in write mode and serialize the dictionary to JSON with UTF-8 encoding
#             with open(file_path, 'w', encoding='utf-8') as file:
#                 json.dump(data, file, indent=4, ensure_ascii=False)
#             #print(f"Dictionary saved successfully to {file_path}")
        
#         elif action == "load":
#             if file_path is None:
#                 raise ValueError("File path must be provided for loading.")
            
#             # Open the file in binary mode first to check content
#             with open(file_path, 'rb') as file:
#                 first_byte = file.read(1)
#                 # Check if the file is likely a text-based JSON file by inspecting the first byte
#                 if first_byte in [b'{', b'[']:
#                     file.seek(0)
#                     # Open the file again in text mode for JSON loading
#                     with open(file_path, 'r', encoding='utf-8') as text_file:
#                         data = json.load(text_file)
#                     #print(f"Dictionary loaded successfully from {file_path}")
#                     return data
#                 else:
#                     raise ValueError("File does not appear to be a valid JSON file. It might be binary or another format.")

#         else:
#             raise ValueError("Action must be either 'save' or 'load'.")
    
#     except (json.JSONDecodeError, ValueError, UnicodeDecodeError) as e:
#         print(f"Error loading JSON file: {e}")
#         return None




if sys.platform == "darwin":
    
    logger.info(f"Running on macOS")
    wdir_path = '/Users/dbosnjakovic/Desktop/python_projects/crawl'
    venv_folder = 'crawl/bin/python'
    curr_v = ''
elif sys.platform == "win32":
    logger.info(f"Running on Windows")
    # It's a Windows PC
    wdir_path = 'C:/Users/dusan/OneDrive/Desktop/pp/test/crawl'
    venv_folder = '.venv/Scripts/python.exe'
    curr_v = 'v6/'
else:
    logger.warning(f"Unsupported OS:{sys.platform}")



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


def evaluate_run_screenshots(workflow_instructions, site_wide_instructions,site_description, run_rerun_path,dimension_info, previous_step_detail, summary, start_time=None):
    extra_instructions = ''
    action_prompt = get_eval_prompt(workflow_instructions, extra_instructions=extra_instructions, site_wide_instructions=site_wide_instructions,site_description = site_description, dimension_info=dimension_info, previous_step_detail=previous_step_detail, summary=summary)
    eval_json,raw = analyze_page_actions(screenshot_path=[f"{run_rerun_path}/chunks/resized_chunk_{dimension_info[0]['id']}.png", f"{run_rerun_path}/dots/resized_final_screenshot.png", f"{run_rerun_path}/temp/resized_chunk_{dimension_info[1]['id']}.png"], prompt=action_prompt, api='claude')

    return eval_json


# Function to analyze raw screenshot
def analyze_raw_screenshot(extra_instructions, site_wide_instructions,site_description, resized_image_path, workflow_instructions, best_image,run_id,advice,last_rerun_advice,summary):
        

    action_prompt = get_page_action_prompt(workflow_instructions, extra_instructions=extra_instructions, site_wide_instructions=site_wide_instructions,site_description=site_description, best_image=best_image,summary=summary,advice = advice,last_rerun_advice = last_rerun_advice)

    #print(f"PROMPT for runID {run_id}: ",action_prompt)

    page_action_json_all,raw = analyze_page_actions(screenshot_path=[resized_image_path], prompt=action_prompt, api='claude')
    #print("Prefilter:",page_action_json_all)

    try:
        page_action_json_ranked = filter_and_rank_outcome(page_action_json_all,best_image)
        
        #print("Postfilter:",page_action_json_all)
        return page_action_json_ranked,action_prompt,page_action_json_all
    except Exception as e:
        logger.info(f"Error in filter_and_rank_outcome: {e}")
        return page_action_json_all,action_prompt,page_action_json_all

import requests

# ... other functions in helper.py ...

# helper.py
def filter_and_rank_outcome(page_action_json_all,best_image):

    modified_data = copy.deepcopy(page_action_json_all)
    modified_data['action_tasks'] = []
    modified_data_loop_over = copy.deepcopy(page_action_json_all)
    ai = 0

    # Ratios for conversion
    # x_ratio = resize_screenshot_result_all_chunks['original_width'] / resize_screenshot_result_all_chunks['new_width']
    # y_ratio = resize_screenshot_result_all_chunks['original_height'] / resize_screenshot_result_all_chunks['new_height']

    for task in modified_data_loop_over['action_tasks']:
        #print(task)
        for candidate in task['candidates']:
            if 'combined_score' not in candidate:
                candidate['combined_score'] = (
                    candidate.get('confidence', 0) * 0.5 +
                    candidate.get('generalizable', 0) * 0.5
                )

            # Convert coordinates to original image space
            if 'coordinates' in candidate and candidate['coordinates'] is not None:

                x_ratio = best_image['original_dimensions']['width'] / best_image['resized_dimensions']['width']
                y_ratio = best_image['original_dimensions']['height'] / best_image['resized_dimensions']['height']
                #print(x_ratio,y_ratio)

                candidate['coordinates_ready_to_act'] = {
                    'x': candidate['coordinates']['x'] * x_ratio,
                    'y': candidate['coordinates']['y'] * y_ratio
                }
                candidate['coordinates_ready_to_draw'] = candidate['coordinates_ready_to_act']

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



def send_action_request(payload, wait_time,run_rerun_path,draw_no_action):
    """
    Sends a POST request to the FastAPI endpoint with the given payload and wait_time.

    :param payload: Dictionary containing the input payload.
    :param wait_time: Integer specifying the wait time between actions.
    :return: Response JSON from the API or an error message.
    """
    url = "http://127.0.0.1:8000/perform-actions"  # Update the URL if the endpoint runs on a different host/port

    try:
        response = requests.post(url, json=payload, params={"wait_time": wait_time, "run_rerun_path": run_rerun_path,"draw_no_action":draw_no_action,    "center_opacity": 0.4,
    "mid_opacity":0.0,
    "outer_opacity":0.5,
    "border_thickness": 4,"diameter": 15})
        
        response.raise_for_status()  # Raise an HTTPError if the response status is 4xx/5xx
        return response.json()
    except requests.RequestException as e:
        #print(f"Error sending action request: {e}")
        logger.error(f"Error sending action request: {e}")
        return None

# helper.py
from PIL import Image, ImageDraw

# --- Helper functions for ipynb ---
def write_track_data(track_data, workflow_path):
    """Helper function to write tracking data to JSON file."""
    try: 
        path_to_use = f"{workflow_path}/tracking.json"
        ensure_writable_file_path(path_to_use)
        with open(path_to_use, "w") as f:
            json.dump(track_data, f, indent=4)
    except Exception as e:
        logger.error(f"Cannot write to {path_to_use}: {e}")
        raise



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
                logger.error(f"Error drawing dots, response code {dot_response.status_code}: {dot_response.json()}")
        except Exception as e:
            logger.error(f"Exception during dot drawing, response code {dot_response.status_code}: {e}")
    
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
            logger.error(f"Error creating highlighted image: {e}")
    else:
        logger.error("No bounding boxes found to highlight")

def create_highlighted_screenshot_cairo(run_rerun_path, bbox_payload,file_for_cairo):
    """
    Creates a highlighted screenshot with all bounding boxes from bbox_payload
    drawn on the same image.
    
    Args:
        run_rerun_path (str): Path to the run folder.
        bbox_payload (dict): Dictionary with bounding boxes for the image.
    """
    # Combine all bounding boxes into one list
    all_bounding_boxes = []
    for _, b_and_st in bbox_payload.items():
        all_bounding_boxes.extend(b_and_st)  # Merge all bounding boxes

    # Define paths
    original_image_path = f"{run_rerun_path}/chunks/{file_for_cairo}"
    highlighted_image_path = f"{run_rerun_path}/highlights/highlights.png"

    # Draw all bounding boxes on the image
    draw_with_cairo(original_image_path, highlighted_image_path, all_bounding_boxes)

def check_coordinates_llm(workflow_instructions,site_wide_instructions,site_description,run_rerun_path,coordinate_info_to_review):
    """Performs LLM analysis to generate action plan."""
    #print("Starting vision analysis")
    final_screenshot_path = f"{run_rerun_path}/dots/final_screenshot.png"

    if not os.path.exists(final_screenshot_path): # Check if the resized image exists
        logger.error(f"Error: final screenshot not found at {final_screenshot_path}")


    coor_check_prompt = f"""
    You are analyzing the following a website ({site_description}) and trying to conduct the following action: 
    {workflow_instructions}

    Keep the following general guidelines about this site in mind:
    {site_wide_instructions}

    Review the following coordinates and determine if they are correctly identified in the screenshot. If not, provide the correct coordinates in the JSON format defined below for each element. You provided the coordinates initially which led to the blue radial dots being drawn where they are. However, you may not be correct and even if the coordinats do seem correct to you, but the blue dots are off, you should calibrate yourself and try to adjust the coordinates toward a more correct position.

    Actions and coordinates you provided intially for the drawn blue dots:
    {coordinate_info_to_review}

    """+"""
    Your Output Schema:
    [
         {
            "action_id": "integer", // action_id referencing the action in the coordinates above.
            "location_of_dot_compared_to_element": "string", // describe where the dot is in relation to the element (e.g. in the upper right corner of the element OR to the right of the element, etc.)
            "dot_identifier_is_over_element": boolean, // true if the blue dot centered around a part of the right element, even if not perfectly
            "dot_identifier_is_not_perfect": boolean,
            "describe_how_to_perfect": "string", // in detail describe how the initial coorinates should be adjusted in terms of directional changes (slightly more right and up) and by what number of pixels.
            "x": "integer", // best new estimate for x coordinate (if needed change)
            "y": "integer" // best new estimate for y coordinate (if needed change)
        }
    ]
    Begin your output in strict JSON-only format now:

    """
    #print(f"PROMPT for runID {run_id}: ",action_prompt)

    coor_check_results,coor_check_raw = analyze_page_actions(screenshot_path=[final_screenshot_path], prompt=coor_check_prompt, api='claude')
    

    if 'results' in coor_check_results:
        coor_check_results = coor_check_results['results']
    #print(f"Total candidates: {len(page_action_json_ranked.get('action_tasks', []))} with lap time: {time.time()-start_time}, about to perform actions")
    return coor_check_results,coor_check_prompt,coor_check_raw




def perform_llm_fold_test(fold_tests,fold_test_paths,workflow_instructions,site_wide_instructions,site_description):
    """Performs LLM analysis to generate action plan."""
    #print("Starting vision analysis")


    for c in fold_test_paths:
        if not os.path.exists(c): # Check if the resized image exists
            logger.error(f"Error: Resized image not found at {c}")
            return None  # Or handle the error appropriately


    page_action_json_ranked,action_prompt,raw = analyze_fold_test(
        fold_tests=fold_tests,
        fold_test_paths=fold_test_paths,workflow_instructions=workflow_instructions,site_wide_instructions=site_wide_instructions,site_description = site_description
    )
    logger.info(f"Completed fold test LLM call")

    if 'results' in page_action_json_ranked:
        page_action_json_ranked = page_action_json_ranked['results']
    #print(f"Total candidates: {len(page_action_json_ranked.get('action_tasks', []))} with lap time: {time.time()-start_time}, about to perform actions")
    return page_action_json_ranked,action_prompt,raw


def get_fold_test_prompt(fold_tests,workflow_instructions,site_wide_instructions,site_description):
    prompt = f"""You are analyzing the following web application: 
    {site_description}

    Keep the following general guidelines about this site in mind: {site_wide_instructions}

    Analyze the following images and determine if you can identify elements necessary to help the user perform the following action in each image. Not all images will have all of the elements necessary:
    User Action:
    {workflow_instructions}
    
    In strict JSON specify how many relevant elements can you identify in each image and if you can locate sufficient elements to help the user perform the actions. Also specify how clearly you think you can identify general elements in each image.
    
    """+"""
    Your Output Schema:
    [{
        "id": "integer", // number part of the Image ID (e.g., 1 for Image 1)
        "relevant_elements": "integer",
        "sufficient_elements": "boolean",
        "clarity": "integer" // 1-5 scale (1: very unclear, 5: very clear)
    },...]

    Begin strict JSON only output now:
    """
    # for test in fold_tests:
    #     prompt += f"Image {test['id']}: Width: {test['width']} / : Height: {test['height']}\n"
    return prompt

# Function to analyze raw screenshot
def analyze_fold_test(
        fold_tests,
        fold_test_paths,workflow_instructions,site_wide_instructions,site_description):
        

    action_prompt = get_fold_test_prompt(fold_tests= fold_tests,workflow_instructions=workflow_instructions,site_wide_instructions=site_wide_instructions,site_description = site_description)

    #print(f"PROMPT for runID {run_id}: ",action_prompt)

    page_action_json_all,raw = analyze_page_actions(screenshot_path=fold_test_paths, prompt=action_prompt, api='claude')
    return page_action_json_all,action_prompt,raw




def perform_llm_analysis(extra_instructions, site_wide_instructions,site_description, run_rerun_path, workflow_instructions, best_image, run_id, start_time,advice,last_rerun_advice,summary):
    """Performs LLM analysis to generate action plan."""
    #print("Starting vision analysis")


    resized_image_path_test = f"{run_rerun_path}/chunks/resized_chunk_{best_image['id']}.png"
    if not os.path.exists(resized_image_path_test): # Check if the resized image exists
        logger.error(f"Error: Resized image not found at {resized_image_path_test}")
    # else:
    #     resized_image_path = resized_image_path_test


    page_action_json_ranked,action_prompt,page_action_json_all = analyze_raw_screenshot(
        extra_instructions,
        site_wide_instructions,site_description,
        resized_image_path_test,
        workflow_instructions,
        best_image=best_image,
        run_id=run_id,
        advice=advice,
        last_rerun_advice = last_rerun_advice,
        summary=summary
    )
    #print(f"Total candidates: {len(page_action_json_ranked.get('action_tasks', []))} with lap time: {time.time()-start_time}, about to perform actions")
    return page_action_json_ranked,action_prompt

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
        logger.error(f"Error during metadata gather: {e}")
        raise


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


def handle_negative_evaluation(eval_json):
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

    return advice,summary


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

def ensure_writable_directory(path: str):
    if not os.path.exists(path):
        raise FileNotFoundError(f"Directory does not exist: {path}")
    if not os.path.isdir(path):
        raise NotADirectoryError(f"Path is not a directory: {path}")
    if not os.access(path, os.W_OK):
        raise PermissionError(f"No write access to directory: {path}")
    
def ensure_writable_file_path(file_path: str):
    directory = os.path.dirname(file_path) or '.'
    ensure_writable_directory(directory)




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
                    logger.error(f"Error fetching metadata: {e}")
                    results[-1]['metadata_error'] = str(e)

                # Test drawing a dot in browser at these coordinates
                try:
                    dot_response = requests.post(
                        'http://127.0.0.1:8000/draw_dots',
                        json=[{'x': viewport_x, 'y': viewport_y}]
                    )
                    results[-1]['dot_draw_result'] = dot_response.json()
                except Exception as e:
                    logger.error(f"Error drawing dot: {e}")
                    results[-1]['dot_error'] = str(e)
                
    # Save results

    path_to_save_to = os.path.join(workflow_step_path, 'coordinate_test_results.json')

    try:
        ensure_writable_file_path(path_to_save_to)
        with open(os.path.join(workflow_step_path, 'coordinate_test_results.json'), 'w') as f:
            json.dump(results, f, indent=2)
    except Exception as e:
        logger.error(f"Cannot write to {path_to_save_to}: {e}")
        raise


    
    return results



def draw_with_cairo(image_path, output_path, bounding_boxes):
    """
    Draw visualization using Cairo with a glowing rectangular effect.
    
    Args:
        image_path (str): Path to the original image.
        output_path (str): Path to save the highlighted image.
        bounding_boxes (list): List of bounding box dictionaries with x, y, width, height.
    """
    from PIL import Image
    import cairo

    # Load the original image and convert it to RGBA
    with Image.open(image_path) as img:
        img = img.convert('RGBA')
        width, height = img.size

        # Convert the PIL image to a format Cairo can use
        img_data = bytearray(img.tobytes('raw', 'BGRa'))

    # Create a Cairo surface using the image data
    surface = cairo.ImageSurface.create_for_data(
        img_data, cairo.FORMAT_ARGB32, width, height, width * 4
    )
    ctx = cairo.Context(surface)

    # Draw bounding boxes with a glowing rectangular effect
    for bbox in bounding_boxes:
        x = bbox['x']
        y = bbox['y']
        w = bbox['width']
        h = bbox['height']

        # Glow effect: multiple expanding rectangles with opacity
        for i in range(15):  # Increase the number of layers for stronger glow
            padding = i * 3  # Adjust the spread for a noticeable effect
            alpha = 0.2 if i < 5 else 0.1 - (i - 5) * 0.01  # Stronger glow for inner layers

            ctx.set_source_rgba(0.2, 0.8, 0.8, max(0, alpha))  # Teal color with fading opacity
            ctx.rectangle(
                x - padding,
                y - padding,
                w + (padding * 2),
                h + (padding * 2)
            )
            ctx.set_line_width(2)
            ctx.stroke()

        # Main rectangle outline (solid color)
        ctx.set_source_rgba(0.2, 0.8, 0.8, 1)  # Solid teal
        ctx.set_line_width(3)
        ctx.rectangle(x, y, w, h)
        ctx.stroke()

    # Save the resulting image
    try:
        surface.write_to_png(output_path)
        logger.info(f"Saved visualization to: {output_path}")
    except Exception as e:
        print(f"Error saving visualization: {e}")
        logger.error(f"Error saving visualization: {e}")
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

def navigate_to_url_from_metadata(full_url):
    """
    Navigates to a specific URL using the /navigate FastAPI endpoint.

    Args:
        url_metadata: The URL metadata dictionary.
    """
    navigation_payload = {"full_url": full_url
    }

    try:
        response = requests.post("http://127.0.0.1:8000/navigate", json=navigation_payload)
        response.raise_for_status()  # Raise an exception for bad status codes
        #print(response.json())
    except requests.exceptions.RequestException as e:
        logger.error(f"Error during navigation: {e}")