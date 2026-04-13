import requests
import json
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


""" ORCHESTRATOR 
It should:

parse arguments
call helper methods
run the workflow in order

Example responsibilities:

load YAML
authenticate
create lab or use existing lab
import topology
start nodes
print result
"""

base_url = "https://10.10.20.161/api/v0" # 192.168.50.238 | 10.10.20.161
USERNAME = "developer"
PWD = "C1sco12345"





def load_yaml():


def genernate_token():

  auth_endpoint = "/authenticate"
  payload = json.dumps({
    "username": f"{USERNAME}",
    "password": f"{PWD}"
  })
  headers = {
    'Content-Type': 'application/json'
  }

  print("Generating token..")
  response = requests.request("POST", f"{base_url}{auth_endpoint}", headers=headers, data=payload, verify=False)
  token = response.json()
  
  print("Token retrieved.")

  return token


def validate_auth():

  headers = {
    'Content-Type': 'application/json',
    'Authorization': f'bearer {token}'
  }

  auth_ok = requests.request("GET", f"{base_url}/authok", headers=headers, verify=False).json()
  if auth_ok == "OK":
    print("Successfully Authenticated.")
    return auth_ok


  


# main
token = genernate_token()
validate_auth()
uid = get_userID()