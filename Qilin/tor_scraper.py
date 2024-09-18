import csv
import time
import re
from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.firefox.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import StaleElementReferenceException, TimeoutException, NoSuchElementException
from stem import Signal
from stem.control import Controller


# Function to request new Tor identity (new IP address)
def renew_tor_identity():
    with Controller.from_port(port=9051) as controller:
        controller.authenticate(password='jiao')
        controller.signal(Signal.NEWNYM) 

# Configure Selenium to use Tor
def get_tor_firefox_browser():
    options = Options()
    options.headless = True 
    options.set_preference('network.proxy.type', 1)
    options.set_preference('network.proxy.socks', '127.0.0.1')
    options.set_preference('network.proxy.socks_port', 9050)
    options.set_preference('network.proxy.socks_remote_dns', True)  
    # Specify the path to the geckodriver
    service = Service('/usr/local/bin/geckodriver')
    browser = webdriver.Firefox(options=options, service=service)
    return browser

def safe_get_text(driver, selector):
    try:
        return driver.find_element(By.CSS_SELECTOR, selector).text
    except NoSuchElementException:
        return "N/A"

def retry_on_stale_element(max_attempts=3):
    def decorator(func):
        def wrapper(*args, **kwargs):
            for attempt in range(max_attempts):
                try:
                    return func(*args, **kwargs)
                except StaleElementReferenceException:
                    if attempt == max_attempts - 1:
                        raise
                    time.sleep(1)
        return wrapper
    return decorator

def get_direct_text(element):
    return ''.join(child.strip() for child in element.find_elements(By.XPATH, './text()') if child.strip())

@retry_on_stale_element(max_attempts=3)
def click_and_scrape(driver, link, processed_companies, csv_writer):
    href = link.get_attribute('href')
    uuid_match = re.search(r'uuid=([^&]+)', href)
    if uuid_match:
        uuid = uuid_match.group(1)
        if uuid in processed_companies:
            #print(f"Skipping already processed company: {link.text}")
            return

    company_name = link.text
    print(f"Scraping: {company_name}")

    link.click()

     # Wait for the page to load
    main_div = WebDriverWait(driver, 20).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, "div.col-md-8.col-xl-6"))
    )
    
    # Extract information
    description_element = driver.find_element(By.CSS_SELECTOR, "div.col-md-8.col-xl-6")
    description = description_element.text.split('\n')[0]
   
    company_url_element = main_div.find_element(By.CSS_SELECTOR, "a.item_box-info__link")
    company_url = company_url_element.get_attribute('href') if company_url_element else "N/A"
    date_added = safe_get_text(driver, "div.item_box-info__item:nth-child(2)")
    view_count = safe_get_text(driver, "div.item_box-info__item:nth-child(3)")
    photos_count = safe_get_text(driver, "div.item_box-info:not(.uppercase) div.item_box-info__item:nth-child(1)")
    files_count = safe_get_text(driver, "div.item_box-info:not(.uppercase) div.item_box-info__item:nth-child(2)")
    data_size = safe_get_text(driver, "div.item_box-info:not(.uppercase) div.item_box-info__item:nth-child(3)")
    
    
    print(f"Description: {description}")
    print(f"URL: {company_url}")
    print(f"Date: {date_added}")
    print(f"Views: {view_count}")
    print(f"Photos: {photos_count}")
    print(f"File Count: {files_count}")
    print(f"Data Size: {data_size}")
    
    # Write to CSV
    csv_writer.writerow([
        company_name, company_url, date_added, view_count,
        photos_count, files_count, data_size, description])

    if uuid:
        processed_companies.add(uuid)

    driver.back()

    # Wait for the main page to reload
    WebDriverWait(driver, 20).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, "a.item_box-title"))
    )

# Scrape the list of companies and click on either 'Company name' or 'Read more'
def scrape_companies(browser, base_url, csv_writer):
    browser.get(base_url)
    
    processed_companies.clear()

    try:
        while True:
            # Find all company title links
            title_links = WebDriverWait(browser, 20).until(
                EC.presence_of_all_elements_located((By.CSS_SELECTOR, "a.item_box-title"))
            )

            for link in title_links:
                try:
                    click_and_scrape(browser, link, processed_companies, csv_writer)
                    print("Progress: " + str(len(processed_companies)) + " / " + str(len(title_links)))
                    #clears cookies so header does not get too long and inputs HTTP 400
                    clear_cookies(browser)
                    
                    if(len(title_links) == len(processed_companies)):
                        print(f"Total unique companies processed naturally: {len(processed_companies)}")
                        return
                except (StaleElementReferenceException, TimeoutException) as e:
                    # Refresh the page and get a new list of links
                    browser.refresh()
                    print(f"Stale or Timeout Error occurred: {e}")
                    break
    finally:
        print(f"Total unique companies processed: {len(processed_companies)}")
       

# Handle pagination and navigate to the next page
def handle_pagination(browser, csv_writer):
    while True:
        try:
            # Locate the 'Next' button using its link text or CSS selector
            next_button = browser.find_element(By.LINK_TEXT, "»")
            print("Next button found. Clicking...")

            # Click the 'Next' button
            browser.execute_script("arguments[0].click();", next_button)
            time.sleep(5)  # Wait for the new page to load
            
            # Scrape the companies on the new page
            scrape_companies(browser, browser.current_url, csv_writer)
        except Exception as e:
            print(f"No more pages or error occurred: {e}")
            break

def clear_cookies(driver):
    driver.delete_all_cookies()
    print("Cookies cleared")
    
# Main function to start scraping
if __name__ == "__main__":
    browser = get_tor_firefox_browser()
    base_url = "http://kbsqoivihgdmwczmxkbovk7ss2dcynitwhhfu5yw725dboqo5kthfaad.onion/"  
    renew_tor_identity()  # Request new IP before starting
    
    # Create or open the CSV file
    with open('scraped_companies.csv', mode='w', newline='', encoding='utf-8') as file:
        csv_writer = csv.writer(file)
        csv_writer.writerow(['Company Name', 'Company URL', 'Date', 'View Count', 'Photo Count', 'File Count', 'File Size', 'Content'])
        processed_companies = set()

        try:
            scrape_companies(browser, base_url, csv_writer)  # Scrape the companies on the first page
            handle_pagination(browser, csv_writer)  # Handle pagination if multiple pages exist
        finally:
            browser.quit()
