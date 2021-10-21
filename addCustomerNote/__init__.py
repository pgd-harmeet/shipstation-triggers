"""
Adds a note indicating that the order has been
sent to WSI order for an order with the specified
order base order number
"""
import azure.functions as func
import os
import requests

async def main(req: func.HttpRequest) -> func.HttpResponse:
    if "orderNumber" not in req.params:
        return func.HttpResponse("Please make sure the orderNumber in your query parameter", status_code=400, mimetype="text/plain")

    session = requests.Session()
    session.headers = {"Authorization": os.environ.get("AUTH_CREDS")}

    try:
        wsi_tag_id = get_wsi_tag(session)
    except AssertionError as e:
        return func.HttpResponse(str(e), status_code=400, mimetype="text/plain")

    orders = session.get(f"https://ssapi4.shipstation.com/orders?orderNumber={req.params['orderNumber']}").json()

    if orders["total"] < 1:
        return func.HttpResponse("There are no orders for this order number", status_code=400, mimetype="text/plain")

    wsi_orders = []
    for order in orders["orders"]:
        if check_order(order, wsi_tag_id): wsi_orders.append(order)

    if len(wsi_orders) == 0:
        return func.HttpResponse(f"Could not find an order with a WSI tag", status_code=400, mimetype="text/plain")

    for order in wsi_orders:
        order["customerNotes"] = "Sent to WSI"
        note_post = session.post("https://ssapi.shipstation.com/orders/createorder", json=order)

        if note_post.status_code != 200:
            return func.HttpResponse("There was an issue adding a note to one of the orders", status_code=400, mimetype="text/plain")

    session.close()

    return func.HttpResponse("Successfully added note", status_code=200, mimetype="text/plain")

def get_wsi_tag(session: requests.Session()) -> int:
    """
    Gets the tag id for the WSI tag

    @param session: A requests.Session() that will facilitate HTTP reqeusts
    @raises AssertionError: If there is no WSI tag found
    @return: A string containing the tag ID for the WSI tag
    """
    tags = session.get(f"https://ssapi.shipstation.com/accounts/listtags").json()

    for tag in tags:
        if tag["name"] == "WSI":
            wsi_tag_id = tag["tagId"]

    assert wsi_tag_id is not None, "Could not find a tag with the name WSI"

    return wsi_tag_id

def check_order(order: dict, tag: int) -> bool:
    """
    Checks an order to see if it has a tag with a matching tagId to the one supplied

    @param order: dict containing information about a singular order
    @param tag: int that is the tag ID of the tag to look for
    @return: bool that is true if the order contains a matching tag
    """
    for tag in order["tagIds"]:
        if tag == tag:
            return True

    return False