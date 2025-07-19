import pandas as pd
import os
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.common.by import By
from selenium.common.exceptions import TimeoutException, NoSuchElementException
import time
import sys

csv_path = "backend/redfin_2025-07-15-06-53-07.csv"

# Read the CSV, skipping the second line (MLS disclaimer)
df = pd.read_csv(csv_path, skiprows=[1])

# Find the column that starts with 'URL'
url_col = [col for col in df.columns if col.startswith("URL")][0]
city_col = [col for col in df.columns if col.lower() == "city"][0]

# Get absolute path to chromedriver.exe (in backend/chromedriver-win64)
project_root = os.path.dirname(os.path.abspath(__file__))
chromedriver_path = os.path.join(project_root, 'chromedriver-win64', 'chromedriver.exe')

# Check if chromedriver.exe exists
if not os.path.isfile(chromedriver_path):
    print(f"ERROR: chromedriver.exe not found at {chromedriver_path}")
    sys.exit(1)

people = []
i = 0
for idx, row in df.iterrows():
    if i > 3:
        break
    url = row[url_col]
    if isinstance(url, pd.Series):
        url = url.iloc[0]
    city = row[city_col]
    if isinstance(city, pd.Series):
        city = city.iloc[0]
    if pd.notna(url) and isinstance(url, str) and url.strip():
        print(f"Visiting: {url}")
        chrome_options = Options()
        chrome_options.add_argument('--start-maximized')
        chrome_options.add_argument('--disable-notifications')
        # chrome_options.add_argument("--headless")  # Uncomment to run headless
        service = Service(executable_path=chromedriver_path)
        driver = webdriver.Chrome(service=service, options=chrome_options)
        wait = WebDriverWait(driver, 10)
        driver.get(url)
        time.sleep(3)  # Wait for page to load
        name = None
        agency = None
        phone = None
        email = None
        agent_url = None
        # First try: main listing page
        try:
            agent_div = wait.until(lambda d: d.find_element(By.CSS_SELECTOR, 'div.agent-info-item[data-rf-test-id="agentInfoItem-agentDisplay"]'))
            # Get agent name
            name_span = agent_div.find_element(By.CSS_SELECTOR, 'span.agent-basic-details--heading span')
            name = name_span.text.strip()
            # Get agency
            agency_span = agent_div.find_element(By.CSS_SELECTOR, 'span.agent-basic-details--broker span')
            agency = agency_span.text.strip()
        except (TimeoutException, NoSuchElementException):
            # Try Redfin agent card
            try:
                agent_card = wait.until(lambda d: d.find_element(By.CSS_SELECTOR, 'div.agent-card-wrapper'))
                # Get agent name
                name_div = agent_card.find_element(By.CSS_SELECTOR, 'div.agent-card-title')
                name = name_div.text.replace('Listed by', '').strip()
                # Get agency
                agency_span = agent_card.find_element(By.CSS_SELECTOR, 'div.agent-info-item span.agent-basic-details--broker span')
                agency = agency_span.text.strip()
                # Try to get agent profile link
                try:
                    agent_link = agent_card.find_element(By.CSS_SELECTOR, 'div.agent-info-item span.agent-basic-details--heading a')
                    agent_url = agent_link.get_attribute('href')
                except NoSuchElementException:
                    agent_url = None
            except (TimeoutException, NoSuchElementException):
                print(f"Agent info not found for {url}")
        # If agent_url found, go to agent profile and scrape more info
        if agent_url:
            try:
                driver.get(agent_url)
                time.sleep(2)
                # Try to get name from agent profile
                try:
                    name_h1 = driver.find_element(By.CSS_SELECTOR, 'div.agent-name h1')
                    name = name_h1.text.strip()
                except NoSuchElementException:
                    pass
                # Try to get phone
                try:
                    phone_a = driver.find_element(By.CSS_SELECTOR, 'a[data-rf-test-name="phone-number"]')
                    phone = phone_a.text.strip()
                except NoSuchElementException:
                    pass
                # Try to get email (if available)
                try:
                    email_a = driver.find_element(By.CSS_SELECTOR, 'a[href^="mailto:"]')
                    email_href = email_a.get_attribute('href')
                    if email_href:
                        email = email_href.replace('mailto:', '').strip()
                except NoSuchElementException:
                    pass
            except Exception as e:
                print(f"Error visiting agent profile: {e}")
        if (not phone or not email) and name and agency and city:
            zillow_options = Options()
            zillow_options.add_argument('--start-maximized')
            zillow_options.add_argument('--disable-notifications')
            zillow_service = Service(executable_path=chromedriver_path)
            zillow_driver = webdriver.Chrome(service=zillow_service, options=zillow_options)
            zillow_wait = WebDriverWait(zillow_driver, 10)
            try:
                zillow_driver.get("https://www.zillow.com/professionals/real-estate-agent-reviews/")
                time.sleep(2)
                # Click the 'Name' button
                name_btn = zillow_wait.until(lambda d: d.find_element(By.XPATH, "//button[@value='name']"))
                name_btn.click()
                # Enter the search string
                search_input = zillow_wait.until(lambda d: d.find_element(By.CSS_SELECTOR, "input[placeholder='Agent name']"))
                search_input.clear()
                search_input.send_keys(f"{name},{agency},{city}")
                # Click the 'Find agent' button
                find_btn = zillow_wait.until(lambda d: d.find_element(By.XPATH, "//button[span[contains(text(),'Find agent')]]"))
                find_btn.click()
                time.sleep(3)
          
            except Exception as e:
                print(f'Zillow lookup failed: {e}')
            zillow_driver.quit()
        person = {
            'name': name,
            'agency': agency,
            'phone': phone,
            'email': email,
            'city': city,
            'property_url': url
        }
        if agent_url:
            person['agent_url'] = agent_url
        people.append(person)
        driver.quit()
        i += 1

print(people) 