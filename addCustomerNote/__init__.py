"""
Adds a note indicating that the order has been
sent to WSI order for an order with the specified
order base order number
"""
import azure.functions as func
import os
import requests
import logging


async def main(msg: func.QueueMessage) -> func.HttpResponse:
    order_number = msg.get_body().decode("utf-8")
    session = requests.Session()
    session.headers = {"Authorization": os.environ.get("AUTH_CREDS")}

    try:
        wsi_tag_id = get_wsi_tag(session)
    except AssertionError as e:
        logging.error("A tag with the name WSI does not exist")
        return func.HttpResponse("A tag with the name WSI does not exist", status_code=400)

    orders = session.get(f"https://ssapi4.shipstation.com/orders?orderNumber={order_number}").json()

    if orders["total"] < 1:
        logging.warn(f"There are no orders for {order_number}")
        return func.HttpResponse(f"There are no orders for {order_number}", status_code=400)

    wsi_orders = []
    for order in orders["orders"]:
        try:
            if check_order(order, wsi_tag_id): wsi_orders.append(order)
        except ValueError:
            logging.warn(f"Order {order['orderNumber']} has no tags associated with it")

    if len(wsi_orders) == 0:
        logging.warn("There were no orders with a WSI tag")
        return func.HttpResponse("There were no orders with a WSI tag", status_code=400)

    for order in wsi_orders:
        order["customerNotes"] = "Sent to WSI"
        note_post = session.post("https://ssapi.shipstation.com/orders/createorder", json=order)

        if note_post.status_code != 200:
            logging.error("There was an issue adding a note to an order")
            return func.HttpResponse("There was an issue adding a note to an order", status_code=400)

    session.close()

    logging.info(f"Successfully added a note to order {order_number}")
    return func.HttpResponse(f"Successfully added a note to order {order_number}", status_code=200)

def get_wsi_tag(session: requests.Session()) -> int:
    """
    Gets the tag id for the WSI tag

    @param session: A requests.Session() that will facilitate HTTP reqeusts
    @raises AssertionError: If there is no WSI tag found
    @return: A string containing the tag ID for the WSI tag
    """
    tags = session.get(f"https://ssapi.shipstation.com/accounts/listtags").json()

    for tag in tags:
        if tag["name"] == "WSI": wsi_tag_id = tag["tagId"]

    assert wsi_tag_id is not None, "Could not find a tag with the name WSI"

    return wsi_tag_id

def check_order(order: dict, tag: int) -> bool:
    """
    Checks an order to see if it has a tag with a matching tagId to the one supplied

    @param order: dict containing information about a singular order
    @param tag: int that is the tag ID of the tag to look for
    @return: bool that is true if the order contains a matching tag
    """
    if order["tagIds"] is None:
        raise ValueError("The order has no associated tags")
    for tag in order["tagIds"]:
        if tag == tag:
            return True

    return False
