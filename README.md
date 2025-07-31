# Web-Based Port Scanner

A self-hosted Flask application that leverages Nmap under the hood to perform on-demand and scheduled port scans of IPv4/IPv6 addresses or networks, right from your browser.

## Features
- **Quick Scan**: Basic single-call scans with version detection (`-sV`) and default NSE scripts (`-sC`)  
- **Threaded Mode**: Fan-out scans across ports or hosts in parallel for faster results  
- **Real-Time Feedback**: Live progress bar and console output pushed over WebSockets via Flask-SocketIO  
- **Scan History**: Persisted SQLite history of past scans with filters by target, mode, date range  
- **Detailed Reports**: Per-host breakdown—OS guess, hostname, MAC, open ports, service versions, NSE script output  
- **Export Results**: Download your scan as JSON, CSV or plain text  
- **Role-Based Access**: Optional login page with user/role support to lock down scans (Default user:pass is admin:pass) 
- **Scheduled Scans**: Create, modify, cancel recurring or one-off scans from the UI, with calendar picker and weekday checkboxes  

## Setup

```bash
git clone https://github.com/isak000w/Web-Port-Scanner/
cd Web-Port-Scanner

# create & activate your virtualenv
python3 -m venv .venv && source .venv/bin/activate

# install dependencies
pip install -r requirements.txt

# run the app
python app.py
```
## Screenshots
Main UI
<img width="1440" height="708" alt="1" src="https://github.com/user-attachments/assets/ff5e6013-b79b-4420-8c63-af529c157a7f" />

Configuring Scan
<img width="1440" height="708" alt="2" src="https://github.com/user-attachments/assets/ff352e76-c32f-44ce-8fc1-02b13bfb2d37" />

Scan Completed
<img width="1440" height="708" alt="3" src="https://github.com/user-attachments/assets/8326a630-635c-45b2-8112-a85997627afc" />

Scan History
<img width="1440" height="708" alt="4" src="https://github.com/user-attachments/assets/638edbb6-bd1b-4d3a-8181-cd213324c01a" />

Scheduling a Scan
<img width="482" height="453" alt="5" src="https://github.com/user-attachments/assets/e982c584-d49b-4e64-badf-1709d770eaea" />

Managing Scheduled Scans
<img width="1440" height="708" alt="6" src="https://github.com/user-attachments/assets/c1ad94de-090d-4cc4-8d99-36d5f9035d55" />
