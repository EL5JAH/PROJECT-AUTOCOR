"""This is where the reusable API methods live.

Example methods:

get_token()
create_lab()
delete_lab()
import_topology()
start_all_nodes()
get_lab()

This keeps your CML API handling reusable across:

deploy
destroy
future status/check scripts"""


import requests
import json
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

base_url = "https://10.10.20.161/api/v0" # 192.168.50.238 | 10.10.20.161
USERNAME = "developer"
PWD = "C1sco12345"

def get_token():

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

def get_userID():

  payload = json.dumps({
    "username": f"{USERNAME}",
    "password": f"{PWD}"
  })

  headers = {
    'Content-Type': 'application/json'
  }

  print("Gathering user info..")
  user = requests.request("POST", f"{base_url}/auth_extended", headers=headers, data=payload, verify=False).json()

  username = user["username"]
  uid = user["id"]
  admin = user["admin"]

  print(f"""
==== RESPONSE ====
User: {username} 
UID: {uid}
Admin: {admin}
==================
""")
  return uid
  

def create_lab():
  """ Must have admin access to CML API with valid license.
      Will not work for sandbox due to lack of permissions """
  
  headers = {
    'Content-Type': 'application/json',
    'Authorization': f'bearer {token}'
  }
  payload = json.dumps({
  "title": "Lab",
  "owner": f"{uid}",
  "description": "Lab from YAML source of truth",
  "notes": "Find why this topology does not perform as expected!",
  "groups": [
    {
      "id": f"{uid}",
      "permission": "read_write"
    }
  ]
})

  response = requests.request("POST", f"{base_url}/labs", headers=headers, data=payload, verify=False).json()

  print(response)


def get_userID():

  payload = json.dumps({
    "username": f"{USERNAME}",
    "password": f"{PWD}"
  })

  headers = {
    'Content-Type': 'application/json'
  }

  print("Gathering user info..")
  user = requests.request("POST", f"{base_url}/auth_extended", headers=headers, data=payload, verify=False).json()

  username = user["username"]
  uid = user["id"]
  admin = user["admin"]

  print(f"""
==== RESPONSE ====
User: {username} 
UID: {uid}
Admin: {admin}
==================
""")
  return uid


  # main
token = genernate_token()
validate_auth()
uid = get_userID()