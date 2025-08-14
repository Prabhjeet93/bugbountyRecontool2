
# Import required libraries
import os
import re
import json
import time
import requests
from urllib.parse import urljoin, urlparse
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
from openpyxl import Workbook


# Constants for file names and directories
URL_FILE = "urls.txt"
SCREENSHOT_DIR = "screenshots"
REPORT_HTML = "report.html"
REPORT_XLSX = "report.xlsx"
# Ensure screenshot directory exists
os.makedirs(SCREENSHOT_DIR, exist_ok=True)


# Setup Excel workbook and summary sheet
wb = Workbook()
summary_sheet = wb.active
summary_sheet.title = "Summary"
summary_sheet.append(["URL", "Status", "Status Code", "Response Time (s)"])



# Setup Selenium Chrome WebDriver in headless mode
#driver = webdriver.Chrome(options=options)
print("[LOG] Initializing Chrome WebDriver...")
options = Options()
driver = webdriver.Chrome(options=options)
options.add_argument("--headless=new")
options.add_argument("--window-size=1920,1080")
driver = webdriver.Chrome(options=options)
print("[LOG] Chrome WebDriver initialized.")


# Load URLs from file
print(f"[LOG] Loading URLs from {URL_FILE} ...")
with open(URL_FILE, "r") as f:
  urls = [line.strip() for line in f if line.strip()]
print(f"[LOG] Loaded {len(urls)} URLs.")


# List to store HTML report entries for each URL
html_entries = []


# Extract JavaScript file URLs, URLs found in JS, and subdomains from a page
def extract_js_data(base_url, soup):
  js_urls = []
  found_urls = set()
  found_subdomains = set()

  domain = urlparse(base_url).netloc

  # Helper to extract URLs from JS text using regex
  def extract_URL(js_text):
    pattern_raw = r"""(?:"|')(
      (
        (?:[a-zA-Z]{1,10}://|//)
        [^"'/]{1,}\.
        [a-zA-Z]{2,}[^"']{0,}
      |
        (?:/|\.\./|\./)
        [^"'><,;| *()%%$^/\\[\]]
        [^"'><,;|()]{1,}
      |
        [a-zA-Z0-9_\-/]{1,}/
        [a-zA-Z0-9_\-/]{1,}\.
        (?:[a-zA-Z]{1,4}|action)
        (?:[\?|/][^"|']{0,}|)
      |
        [a-zA-Z0-9_\-]{1,}\.
        (?:php|asp|aspx|jsp|json|action|html|js|txt|xml)
        (?:\?[^"|']{0,}|)
      )
    )(?:"|')"""
    pattern = re.compile(pattern_raw, re.VERBOSE)
    return [match.group(1) for match in pattern.finditer(js_text)]

  # Find all script tags with src attribute
  scripts = soup.find_all("script", src=True)
  for script in scripts:
    src = script['src']
    full_url = urljoin(base_url, src)
    js_urls.append(full_url)
    try:
      r = requests.get(full_url, timeout=5)
      js_text = r.text
      urls_in_js = extract_URL(js_text)
      found_urls.update(urls_in_js)
      # Find subdomains in JS URLs
      subdomains = [u for u in urls_in_js if domain in u and urlparse(u).netloc != domain]
      found_subdomains.update(subdomains)
    except:
      continue

  return list(js_urls), list(found_urls), list(found_subdomains)


# Main loop: process each URL
for url in urls:
  print(f"[LOG] Processing URL: {url}")
  # Initialize variables for each URL
  status = "Success"
  status_code = 0
  response_time = 0
  error_msg = ""
  headers = {}
  links = []
  buttons = []
  textboxes = []
  forms = []
  images = []
  meta_tags = {}
  page_title = ""
  screenshot_path = ""
  js_files = []
  js_urls = []
  js_subdomains = []
  cookies = []
  try:
    # Send HTTP request to the URL
    print(f"[LOG] Sending HTTP request to: {url}")
    start = time.time()
    response = requests.get(url, timeout=10)
    print(f"[LOG] Received response: {response.status_code} in {round(time.time() - start, 2)}s")
    response_time = round(time.time() - start, 2)
    status_code = response.status_code
    headers = dict(response.headers)
    # Check for non-200 status code
    if status_code != 200:
      status = "Error"
      print(f"[ERROR] Non-200 status code: {status_code} for {url}")
      raise Exception(f"Non-200 status code: {status_code}")
    # Mark slow responses
    if response_time > 5:
      status = "Slow"
      print(f"[WARN] Slow response for {url}: {response_time}s")
    # Load page in Selenium WebDriver
    print(f"[LOG] Loading page in Selenium: {url}")
    driver.get(url)
    time.sleep(3)
    # Try to accept cookies if a consent button is present
    print(f"[LOG] Attempting to accept cookies if present.")
    keywords = ["accept", "accept all", "agree", "got it", "allow", "ok"]
    for keyword in keywords:
      xpath = f"//*[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), '{keyword}')]"
      try:
        btn = WebDriverWait(driver, 3).until(EC.element_to_be_clickable((By.XPATH, xpath)))
        btn.click()
        print(f"[LOG] Accepted cookies with keyword: {keyword}")
        break
      except:
        continue
    # Get cookies from the browser
    print(f"[LOG] Page loaded. Fetching cookies.")
    cookies = driver.get_cookies()
    print(f"[LOG] Fetched {len(cookies)} cookies.")
    # Take a full-page screenshot
    print(f"[LOG] Taking full-page screenshot.")
    S = lambda X: driver.execute_script(f'return document.body.parentNode.scroll{X}')
    driver.set_window_size(S('Width'), S('Height'))
    screenshot_name = url.replace("https://", "").replace("http://", "").replace("/", "_") + ".png"
    screenshot_path = os.path.join(SCREENSHOT_DIR, screenshot_name)
    driver.save_screenshot(screenshot_path)
    print(f"[LOG] Screenshot saved: {screenshot_path}")
    # Parse page HTML with BeautifulSoup
    print(f"[LOG] Parsing page HTML.")
    soup = BeautifulSoup(driver.page_source, "html.parser")
    page_title = soup.title.string.strip() if soup.title else ""
    # Extract page elements
    links = [a['href'] for a in soup.find_all('a', href=True)]
    buttons = [btn.text.strip() for btn in soup.find_all('button')]
    textboxes = [inp.get('name') or inp.get('id') or 'Unnamed' for inp in soup.find_all('input') if inp.get('type') in ['text', 'email', 'password']]
    forms = [str(form)[:100] for form in soup.find_all('form')]
    images = [img['src'] for img in soup.find_all('img', src=True)]
    # Extract meta tags (description, keywords)
    for meta in soup.find_all('meta'):
      if meta.get('name') in ['description', 'keywords']:
        meta_tags[meta.get('name')] = meta.get('content')
    # Extract JS file URLs, JS URLs, and subdomains
    print(f"[LOG] Extracting JS data.")
    js_files, js_urls, js_subdomains = extract_js_data(url, soup)
    # Create a sanitized sheet name for Excel
    sheet_name = re.sub(r'https?://', '', url)
    sheet_name = re.sub(r'[^a-zA-Z0-9]', '_', sheet_name)[:31]
    sheet = wb.create_sheet(title=sheet_name)
    sheet.append(["Text Fields", "Buttons", "JS Subdomains", "Links", "JS URLs"])
    # Write extracted data to Excel sheet
    for i in range(max(len(textboxes), len(buttons), len(links), len(js_urls), len(js_subdomains))):
      sheet.append([
        textboxes[i] if i < len(textboxes) else "",
        buttons[i] if i < len(buttons) else "",
        js_subdomains[i] if i < len(js_subdomains) else "",
        links[i] if i < len(links) else "",
        js_urls[i] if i < len(js_urls) else ""
      ])
    print(f"[LOG] Finished processing {url}")
  except Exception as e:
    # Handle errors for this URL
    status = "Failed"
    error_msg = str(e)
    print(f"[ERROR] Exception for {url}: {error_msg}")
  # Add summary and details to Excel and HTML report data
  summary_sheet.append([url, status, status_code, response_time])
  html_entries.append({
    "url": url,
    "status": status,
    "status_code": status_code,
    "response_time": response_time,
    "headers": headers,
    "title": page_title,
    "forms": forms,
    "images": images,
    "meta": meta_tags,
    "links": links,
    "buttons": buttons,
    "textboxes": textboxes,
    "js_files": js_files,
    "js_urls": js_urls,
    "js_subdomains": js_subdomains,
    "cookies": cookies,
    "screenshot": screenshot_path.replace("\\", "/") if screenshot_path else "",
    "error": error_msg
  })


# Close Selenium WebDriver and save Excel report
print("[LOG] Quitting Chrome WebDriver...")
driver.quit()
print("[LOG] Chrome WebDriver closed.")
print(f"[LOG] Saving Excel report: {REPORT_XLSX}")
wb.save(REPORT_XLSX)
print(f"[LOG] Excel report saved: {REPORT_XLSX}")


# Generate HTML report from collected data
html_template = """
<!DOCTYPE html>
<html>
<head>
  <title>Bug Bounty Report</title>
  <style>
    body {{ font-family: Arial; display: flex; }}
    .left {{ width: 30%; background: #f4f4f4; padding: 10px; overflow-y: auto; height: 100vh; }}
    .right {{ width: 70%; padding: 10px; overflow-y: auto; height: 100vh; }}
    .url {{ margin: 5px 0; cursor: pointer; }}
    .green {{ color: green; }}
    .red {{ color: red; }}
    .yellow {{ color: orange; }}
    .popup {{ display: none; position: fixed; top: 10%; left: 20%; width: 60%; background: white; border: 1px solid #ccc; padding: 10px; z-index: 999; }}
    .popup ul {{ max-height: 300px; overflow-y: auto; }}
    .popup button {{ float: right; }}
    pre {{ background: #eee; padding: 10px; }}
  </style>
  <script>
    function showDetails(index) {{
      const data = window.reportData[index];
      let colorClass = data.status === "Success" ? "green" : (data.status === "Failed" ? "red" : "yellow");
      document.getElementById("details").innerHTML = `
        <h2>${{data.url}}</h2>
        <p>Status: <span class="${{colorClass}}">${{data.status}}</span></p>
        <p>Status Code: ${{data.status_code}}</p>
        <p>Response Time: ${{data.response_time}} seconds</p>
        <p>Title: ${{data.title}}</p>
        <p>Forms: ${{data.forms.length}}</p>
        <p>Images: ${{data.images.length}}</p>
        <p><a href="${{data.screenshot}}" target="_blank">View Screenshot</a></p>
        <p><a href="#" onclick="showPopup('links', ${{index}})">Links (${{data.links.length}})</a></p>
        <p>JS URLs: <a href="#" onclick="showPopup('js_urls', ${{index}})">${{data.js_urls.length}}</a></p>
        <p>JS Subdomains: <a href="#" onclick="showPopup('js_subdomains', ${{index}})">${{data.js_subdomains.length}}</a></p>
        <p>Meta Tags:</p>
        <ul>
          ${{Object.entries(data.meta).map(([k,v]) => `<li><strong>${{k}}:</strong> ${{v}}</li>`).join('')}}
        </ul>
        <p>Cookies: <a href="#" onclick="showPopup('cookies', ${{index}})">${{data.cookies.length}}</a></p>
        <p>Headers:</p>
        <pre>${{JSON.stringify(data.headers, null, 2)}}</pre>
      `;
      }}
    function showPopup(type, index) {{
      const data = window.reportData[index];
      const items = data[type];
        let html = '';
        if (type === 'cookies') {{
          html += `<h3>COOKIES of ${{data.url}} (${{items.length}})</h3><ul>`;
          html += items.map(cookie => `<li><strong>${{cookie.name}}:</strong> ${{cookie.value}}</li>`).join('');
          html += '</ul>';
        }} else {{
          html += `<h3>${{type.toUpperCase()}} of ${{data.url}} (${{items.length}})</h3><ul>`;
          html += items.map(item => `<li>${{item}}</li>`).join('');
          html += '</ul>';
        }}
        html += '<button onclick="closePopup()">Close</button>';
        document.getElementById("popup-content").innerHTML = html;
        document.getElementById("popup").style.display = "block";
    }}

    function closePopup() {{
      document.getElementById("popup").style.display = "none";
    }}

    window.onload = function() {{
      const container = document.getElementById("url-list");
      window.reportData.forEach((entry, i) => {{
        const div = document.createElement("div");
        div.className = `url ${{entry.status === "Success" ? "green" : (entry.status === "Failed" ? "red" : "yellow")}}`;
        div.textContent = entry.url;
        div.onclick = () => showDetails(i);
        container.appendChild(div);
      }});
    }}

    window.reportData = {json_data};
  </script>
</head>
<body>
  <div class="left" id="url-list"></div>
  <div class="right" id="details"></div>
  <div class="popup" id="popup">
    <div id="popup-content"></div>
  </div>
</body>
</html>
""".format(json_data=json.dumps(html_entries))

# Write HTML report to file
print(f"[LOG] Writing HTML report: {REPORT_HTML}")
with open(REPORT_HTML, "w", encoding="utf-8") as f:
  f.write(html_template)
print(f"[LOG] HTML report saved: {REPORT_HTML}")
