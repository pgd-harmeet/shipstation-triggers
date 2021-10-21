"""
Creates an Eagle order sheet to be inserted into the Eagle system for inventory tracking
Uses the structure specified in d112-021 ESTU format.doc
"""

import azure.functions as func
import os
import requests

async def main(req: func.HttpRequest) -> func.HttpResponse:
    # Ensure all parameters are in the request
    if "note" not in req.params or "orderNumber" not in req.params:
        return func.HttpResponse("Please make sure to include both note & orderNumber in your query parameters",
            status_code=400,
            mimetype="text/plain")

    orders = requests.get(f"https://ssapi4.shipstation.com/orders?orderNumber={req.params['orderNumber']}",
        headers={"Authorization": os.environ.get("AUTH_CREDS")}).json()
    tags = requests.get(f"https://ssapi.shipstation.com/accounts/listtags").json()

    for tag in tags:
        if tag["name"] == "WSI": wsi_tag_id = tag["tagId"]

    if wsi_tag_id is None:
        return func.HttpResponse("There is no tag with the name WSI", status_code=501, mimetype="text/plain")

    for order in orders:
        for tag in order["tagIds"]:
            if tag == wsi_tag_id: order_info = order

    if order_info is None:
        return func.HttpResponse(f"Could not find an order with a WSI tag", status_code=400, mimetype="text/plain")

    order_info["customerNotes"] = "Sent to WSI"
    ss_post = requests.post("https://ssapi.shipstation.com/orders/createorder",
        json=order_info,
        headers={"Authorization": os.environ.get("AUTH_CREDS")})

    if (ss_post.status_code != 200):
        return func.HttpResponse("There was an issue adding a note, please check the logs", status_code=400, mimetype="text/plain")

    return func.HttpResponse("Successfully added note", status_code=200, mimetype="text/plain")
