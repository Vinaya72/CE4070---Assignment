import csv
from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.common.by import By
from stem import Signal
from stem.control import Controller
import time

# Function to request new Tor identity (new IP address)
def renew_tor_identity():
    with Controller.from_port(port=9051) as controller:
        controller.authenticate()
        controller.signal(Signal.NEWNYM) 

# Configure Selenium to use Tor
def get_tor_firefox_browser():
    options = Options()
    options.headless = True  # Run in headless mode (no GUI)
    options.set_preference('network.proxy.type', 1)
    options.set_preference('network.proxy.socks', '127.0.0.1')
    options.set_preference('network.proxy.socks_port', 9050)
    options.set_preference('network.proxy.socks_remote_dns', True)  
    browser = webdriver.Firefox(options=options)
    return browser

# Scrape the list of companies and click on either 'Company name' or 'Read more'
def scrape_companies(browser, base_url, csv_writer):
    browser.get(base_url)
    time.sleep(5)  # Give time for the page to load

    # Loop through each company entry and click the 'Read more' button
    companies = browser.find_elements(By.CSS_SELECTOR, "section.list-item h1.title")

    for company in companies:
        title = company.text
        print(f"Scraping: {title}")

        # Click the 'Company Name' (since it also leads to the same page)
        company_link = company.find_element(By.XPATH, "..//a")
        browser.execute_script("arguments[0].click();", company_link)
        time.sleep(5)  # Wait for the new page to load

        # Extract the content on the new page, excluding header information
        body = browser.find_element(By.TAG_NAME, 'body').text
        content = remove_header_and_zip_links(body)

        # Save the company name and content in the CSV file
        csv_writer.writerow([title, content])
        
        # Go back to the main list page
        browser.back()
        time.sleep(5)

# Function to remove header and count ZIP file links
def remove_header_and_zip_links(page_content):
    lines = page_content.split("\n")
    filtered_content = []
    zip_file_counts = {}

    # Start filtering content after the header section (ignoring the first few lines)
    header_ended = False
    for line in lines:
        # Detect when the header ends (this example assumes it's the line after "Email")
        if "Email:" in line:
            header_ended = True
            continue

        if not header_ended:
            continue

        # Check for zip file sections and count ZIP links
        if "zip" in line.lower():
            zip_section = line.strip().split()[0]  # Get the section name (e.g., "Business data")
            zip_file_count = line.lower().count(".zip")  # Count the .zip occurrences

            if zip_file_count > 0:
                zip_file_counts[zip_section] = zip_file_count
        else:
            filtered_content.append(line)

    # Add the ZIP file counts at the end of the content
    if zip_file_counts:
        filtered_content.append("\n--- ZIP File Summary ---")
        for section, count in zip_file_counts.items():
            filtered_content.append(f"{section}: {count} zip files")

    return "\n".join(filtered_content)

# Handle pagination and navigate to the next page
def handle_pagination(browser, csv_writer):
    while True:
        try:
            # Locate the 'Next' button using its link text or CSS selector
            next_button = browser.find_element(By.LINK_TEXT, "Next →")
            print("Next button found. Clicking...")

            # Click the 'Next' button
            browser.execute_script("arguments[0].click();", next_button)
            time.sleep(5)  # Wait for the new page to load
            
            # Scrape the companies on the new page
            scrape_companies(browser, browser.current_url, csv_writer)
        except Exception as e:
            print(f"No more pages or error occurred: {e}")
            break

# Main function to start scraping
if __name__ == "__main__":
    browser = get_tor_firefox_browser()
    base_url = "http://bianlivemqbawcco4cx4a672k2fip3guyxudzurfqvdszafam3ofqgqd.onion/"  

    # Create or open the CSV file
    with open('bianlian.csv', mode='w', newline='', encoding='utf-8') as file:
        csv_writer = csv.writer(file)
        csv_writer.writerow(['Company Name', 'Content'])

        try:
            renew_tor_identity()  # Request new IP before starting
            scrape_companies(browser, base_url, csv_writer)  # Scrape the companies on the first page
            handle_pagination(browser, csv_writer)  # Handle pagination if multiple pages exist
        finally:
            browser.quit()