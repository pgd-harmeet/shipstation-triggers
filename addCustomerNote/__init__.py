"""
Creates an Eagle order sheet to be inserted into the Eagle system for inventory tracking
Uses the structure specified in d112-021 ESTU format.doc
"""

import azure.functions as func
import os
import requests

async def main(req: func.HttpRequest) -> func.HttpResponse:
    ss_res = requests.get(f"https://ssapi4.shipstation.com/orders?orderNumber={req.params['orderNumber']}",
        headers={"Authorization": os.environ.get("AUTH_CREDS")}).json()
    order_info = ss_res["orders"][0]

    if "note" in req.params:
        order_info["customerNotes"] = req.params["note"]
    else:
        order_info["customerNotes"] = ""

    ss_post = requests.post("https://ssapi.shipstation.com/orders/createorder",
        json=order_info,
        headers={"Authorization": os.environ.get("AUTH_CREDS")})

    if (ss_post.status_code != 200):
        return func.HttpResponse("There was an issue adding a note, please check the logs", status_code=400, mimetype="text/plain")

    return func.HttpResponse("Successfully added note", status_code=200, mimetype="text/plain")
