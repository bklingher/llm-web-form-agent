import os
import time
import argparse
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import Select
from selenium.common.exceptions import TimeoutException, NoSuchElementException
import openai
import logging
import json
from datetime import datetime

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class FormFillingAgent:
    def __init__(self, form_url, data, api_key=None):
        self.form_url = form_url
        self.data = data
        self.driver = None
        
        # Initialize OpenAI client
        if api_key:
            self.client = openai.OpenAI(api_key=api_key)
        else:
            self.client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        
        # Initialize Chrome WebDriver
        chrome_options = Options()
        # Uncomment the line below for headless mode
        # chrome_options.add_argument("--headless")
        chrome_options.add_argument("--window-size=1920,1080")
        chrome_options.add_argument("--start-maximized")
        
        self.driver = webdriver.Chrome(options=chrome_options)
        self.wait = WebDriverWait(self.driver, 10)
    
    def navigate_to_form(self):
        """Navigate to the form URL"""
        logger.info(f"Navigating to {self.form_url}")
        self.driver.get(self.form_url)
        time.sleep(2)  # Wait for page to load
    
    def analyze_form(self):
        """Use LLM to analyze the form structure and create a mapping strategy"""
        logger.info("Analyzing form structure...")
        
        # Get page source
        page_source = self.driver.page_source
        logger.info(f"Page source length: {len(page_source)}")
        
        # Find all form elements
        form_elements = self.driver.find_elements(By.XPATH, "//input | //select | //textarea")
        logger.info(f"Found {len(form_elements)} form elements")
        
        element_details = []
        for idx, element in enumerate(form_elements, 1):
            try:
                element_type = element.get_attribute("type")
                element_id = element.get_attribute("id")
                element_name = element.get_attribute("name")
                element_label_text = ""
                
                logger.info(f"\nProcessing element {idx}:")
                logger.info(f"Type: {element_type}")
                logger.info(f"ID: {element_id}")
                logger.info(f"Name: {element_name}")
                
                # Try to find associated label
                if element_id:
                    label_elements = self.driver.find_elements(By.XPATH, f"//label[@for='{element_id}']")
                    if label_elements:
                        element_label_text = label_elements[0].text
                        logger.info(f"Found label text: {element_label_text}")
                    else:
                        logger.info("No label found for this element")
                
                # Get placeholder text
                placeholder = element.get_attribute("placeholder")
                logger.info(f"Placeholder: {placeholder}")
                
                # Get parent container text for context
                parent_text = ""
                try:
                    parent = element.find_element(By.XPATH, "./parent::*")
                    parent_text = parent.text
                    logger.info(f"Parent text: {parent_text}")
                except Exception as e:
                    logger.warning(f"Could not get parent text: {str(e)}")
                
                element_details.append({
                    "type": element_type,
                    "id": element_id,
                    "name": element_name,
                    "label": element_label_text,
                    "placeholder": placeholder,
                    "parent_text": parent_text
                })
            except Exception as e:
                logger.error(f"Error processing element {idx}: {str(e)}")
                continue
        
        logger.info("\nPreparing LLM prompt with collected details:")
        logger.info(f"Total elements collected: {len(element_details)}")
        
        # Prepare the prompt for the LLM
        prompt = f"""
        I need to map my data to form fields on a webpage. Below are the form elements I found:
        
        {json.dumps(element_details, indent=2)}
        
        Here is my data that I need to fill in the form:
        
        {json.dumps(self.data, indent=2)}
        
        Please create a mapping strategy that matches my data fields to the appropriate form elements.
        The output should be a JSON object where keys are the form element identifiers (prefer id, then name)
        and values are the corresponding data values from my dataset.
        
        Format your response as a valid JSON object ONLY, with no explanation text before or after.
        Do NOT include any fields that would indicate signing the form as a representative of any entity.
        """
        
        logger.info("Sending request to LLM...")
        
        # Query the LLM
        try:
            response = self.client.chat.completions.create(
                model="gpt-4-turbo",  # or another appropriate model
                messages=[
                        {"role": "system", "content": "You are a helpful assistant that specializes in web form automation. Given form elements and data, you match data fields to appropriate form inputs. Always respond with valid JSON only."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=2000
            )
        
            # Debug the raw response
            raw_content = response.choices[0].message.content
            logger.info("Raw LLM response received:")
            logger.info(f"Response type: {type(raw_content)}")
            logger.info(f"Response length: {len(raw_content) if raw_content else 0}")
            logger.info(f"First 100 chars: {raw_content[:100] if raw_content else 'Empty response'}")
            
            # Try to clean the response if needed
            cleaned_content = raw_content.strip()
            
            # Check if the content starts with a code block marker
            if cleaned_content.startswith("```json"):
                # Extract JSON from code block
                json_start = cleaned_content.find("\n") + 1
                json_end = cleaned_content.rfind("```")
                if json_end > json_start:
                    cleaned_content = cleaned_content[json_start:json_end].strip()
            
            logger.info(f"Cleaned content: {cleaned_content[:100]}...")
            
            # Now try to parse the JSON
            try:
                mapping_strategy = json.loads(cleaned_content)
                logger.info("Successfully parsed LLM response as JSON")
                logger.info("Mapping strategy:")
                logger.info(json.dumps(mapping_strategy, indent=2))
                return mapping_strategy
            except json.JSONDecodeError as e:
                logger.error(f"JSON parsing error: {str(e)}")
                logger.error(f"Could not parse response as JSON. Full response: {cleaned_content}")
                
                # Fallback strategy: create a basic mapping
                return self.create_fallback_mapping(element_details)
            
        except Exception as e:
            # TODO: Implement fallback strategy if LLM request fails completely
            logger.error(f"Error in LLM request: {str(e)}")

    def fill_form(self, mapping_strategy):
        """Fill the form using the mapping strategy provided by the LLM"""
        logger.info("Filling form with provided data...")
        
        for field_id, value in mapping_strategy.items():
            try:
                # Skip empty values
                if value is None or value == "":
                    continue
                
                # Find the element
                element = None
                try:
                    element = self.driver.find_element(By.ID, field_id)
                except NoSuchElementException:
                    try:
                        element = self.driver.find_element(By.NAME, field_id)
                    except NoSuchElementException:
                        try:
                            element = self.driver.find_element(By.XPATH, f"//input[@placeholder='{field_id}']")
                        except NoSuchElementException:
                            logger.warning(f"Could not find element with identifier: {field_id}")
                            continue
                
                # Handle different input types
                element_type = element.get_attribute("type")
                
                if element_type == "checkbox":
                    if value in [True, "yes", "Y", "true"]:
                        if not element.is_selected():
                            element.click()
                elif element_type == "radio":
                    if str(value).lower() in ["true", "yes", "y", "1"]:
                        element.click()
                elif element.tag_name == "select":
                    select = Select(element)
                    try:
                        select.select_by_visible_text(str(value))
                    except:
                        try:
                            select.select_by_value(str(value))
                        except:
                            logger.warning(f"Could not select value {value} for {field_id}")
                else:
                    # Clear existing text for text inputs
                    element.clear()
                    element.send_keys(str(value))
                
                logger.info(f"Filled field {field_id} with value: {value}")
                time.sleep(0.2)  # Small delay between fields to avoid overwhelming the form
                
            except Exception as e:
                logger.error(f"Error filling field {field_id}: {str(e)}")
        
        logger.info("Form filling complete.")
    
    def submit_form(self):
        """Find and click the submit button"""
        logger.info("Looking for submit button...")
        
        # Common submit button selectors
        submit_selectors = [
            "//button[@type='submit']",
            "//input[@type='submit']",
            "//button[contains(text(), 'Submit')]",
            "//button[contains(text(), 'send')]",
            "//button[contains(@class, 'submit')]",
            "//input[contains(@value, 'Submit')]"
        ]
        
        for selector in submit_selectors:
            try:
                submit_button = self.driver.find_element(By.XPATH, selector)
                logger.info(f"Submit button found with selector: {selector}")
                
                # Ask LLM if we should proceed with submission
                form_data = {}
                form_elements = self.driver.find_elements(By.XPATH, "//input | //select | //textarea")
                
                for element in form_elements:
                    element_id = element.get_attribute("id") or element.get_attribute("name")
                    if element_id:
                        if element.get_attribute("type") == "checkbox":
                            form_data[element_id] = element.is_selected()
                        elif element.get_attribute("type") == "radio":
                            if element.is_selected():
                                form_data[element_id] = True
                        else:
                            form_data[element_id] = element.get_attribute("value")
                
                prompt = f"""
                I've filled out a form with the following data:
                
                {json.dumps(form_data, indent=2)}
                
                Original data I intended to use:
                
                {json.dumps(self.data, indent=2)}
                
                Should I proceed with submission? Are there any issues or missing required fields?
                Is there anything that looks like signing as a representative that I should avoid?
                
                Please respond with "PROCEED" if everything looks good for submission,
                or "STOP" followed by the reason if there are issues that should be addressed before submission.
                """
                
                response = self.client.chat.completions.create(
                    model="gpt-4-turbo",
                    messages=[
                        {"role": "system", "content": "You are a helpful assistant that analyzes form data before submission to ensure completeness and compliance with requirements."},
                        {"role": "user", "content": prompt}
                    ],
                    max_tokens=500
                )
                
                decision = response.choices[0].message.content
                
                if "PROCEED" in decision:
                    logger.info("LLM approved form submission. Submitting form...")
                    submit_button.click()
                    time.sleep(3)  # Wait for submission to complete
                    logger.info("Form submitted successfully.")
                    return True
                else:
                    reason = decision.replace("STOP", "").strip()
                    logger.warning(f"LLM advised against submission: {reason}")
                    return False
                
            except NoSuchElementException:
                continue
            except Exception as e:
                logger.error(f"Error during form submission: {str(e)}")
                return False
        
        logger.warning("Could not find submit button.")
        return False
    
    def run(self):
        """Run the entire form filling process"""
        try:
            self.navigate_to_form()
            mapping_strategy = self.analyze_form()
            self.fill_form(mapping_strategy)
            submitted = self.submit_form()
            
            if submitted:
                # Take screenshot of the result
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                screenshot_path = f"form_submission_{timestamp}.png"
                self.driver.save_screenshot(screenshot_path)
                logger.info(f"Screenshot saved to {screenshot_path}")
            
            return submitted
        finally:
            # Keep the browser open for a while to see the results
            time.sleep(5)
            self.driver.quit()
            
            
mock_data = {
    "attorney": {
        "online_account_number": "A123456789",
        "family_name": "Doe",
        "first_name": "John",
        "middle_name": "Michael",
        "address_line_1": "123 Legal Avenue",
        "unit_type": "Ste",
        "address_line_2": "405",
        "city": "Boston",
        "state": "Massachusetts",
        "zip_code": "02108",
        "province": "",
        "country": "United States",
        "daytime_phone": "(617) 555-7890",
        "email": "mdoe@legalfirm.com",
        "fax": "6175554321",
        "attorney_eligible": "yes",
        "licensing_state": "MA",
        "bar_number": "BBO#654321",
        "subject_to_restrictions": "no",
        "law_firm": "Doe & Associates Legal Group",
        "is_nonprofit_rep": False,
        "org_name": "",
        "accreditation_date": "",
        "associated_with_student": "no",
        "law_student": "",
        "administrative_case": True,
        "administrative_matter": "I-485 Application to Register Permanent Residence",
        "civil_case": False,
        "civil_matter": "",
        "other_legal": False,
        "other_legal_matter": "",
        "receipt_number": "MSC2190123456",
        "client_type": "Beneficiary",
    },
    "client": {
        "family_name": "Jones",
        "first_name": "Jane",
        "entity_name": "",
        "entity_title": "",
        "reference_number": "GRC-2023-0045",
        "id_number": "A087654321",
        "daytime_phone": "8575556789",
        "mobile_phone": "8575559876",
        "email": "jane.jones@email.com",
        "address_line_1": "45 Commonwealth Avenue",
        "unit_type": "",
        "address_line_2": "",
        "city": "Boston",
        "state": "MA",
        "zip_code": "02116",
        "province": "",
        "country": "US",
        "send_notices_to_attorney": "Y",
        "send_documents_to_attorney": "Y",
        "send_documents_to_client": "N",
        "signature_date": "",
    },
    "attorney_signature_date": "",
    "additional_signature_date": "",
    "part6": {
        "additional_info": {
            "family_name": "Johnson",
            "given_name": "Sarah",
            "middle_name": "Elizabeth",
            "entries": [
                {
                    "page_number": "1",
                    "part_number": "2",
                    "item_number": "1.a",
                    "additional_info": "Also licensed in New York State Bar, Bar #NY7654321",
                }
            ],
        }
    },
}


def main():
    parser = argparse.ArgumentParser(description='Web Form Filling Agent')
    parser.add_argument('--url', type=str, default="https://mendrika-alma.github.io/form-submission/",
                        help='URL of the form to fill')
    parser.add_argument('--data_file', type=str, help='JSON file containing form data')
    parser.add_argument('--api_key', type=str, help='OpenAI API key')
    
    args = parser.parse_args()
    
    # Load data
    if args.data_file:
        with open(args.data_file, 'r') as f:
            data = json.load(f)
    else:
        # Use mock data if no file is provided
        data = mock_data
    
    # Initialize and run agent
    agent = FormFillingAgent(args.url, data, args.api_key)
    agent.run()


if __name__ == "__main__":
    main()