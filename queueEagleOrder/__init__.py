"""
Queues a resouce_url from ShipStation to create an Eagle order sheet for.
Any resouce clean up and checking should be done in this trigger to avoid
slowing down order creation process.

DOES NOT CHECK IF THE ORDER EXISTS IN MAGENTO, LEAVE THAT FOR THE QUEUE
TO HANDLE
"""
import azure.functions as func
import logging
import os
import requests

def main(req: func.HttpRequest, msg: func.Out[func.QueueMessage]) -> func.HttpResponse:
  req = req.get_json()
  resource_url = req["resource_url"]
  resource_type = req["resource_type"]
  logging.info(resource_url)

  if resource_type != "SHIP_NOTIFY":
    logging.warn("The resource is not a SHIP_NOTIFY resource")
    return func.HttpResponse("The resource is not a SHIP_NOTIFY resource", status_code=400)

  resource_url = resource_url.replace('includeShipmentItems=False', 'includeShipmentItems=True')
  try:
    validate_order(resource_url)
  except ValueError as e:
    logging.info(f"Unable to queue resource_url: {str(e)}")
    return func.HttpResponse(str(e), status_code=400)

  msg.set(resource_url)
  logging.info(f"{resource_url} successfully queued")
  return func.HttpResponse("Successfully queued this resource URL", status_code=200)

def validate_order(resource_url) -> None:
  """Validates order information

  Checks for:
  - Nonzero number of shipments associated to url
  - If order belongs to New Amazon or New Magento store
  - If shipment has any items associated with it
  - If all shipment items have a nonzero quantity or unit price

  Args:
    resource_url (str): The URL containing information for a shipment

  Raises:
    ValueError: The resource URL has no shipments associated with it
    ValueError: The order does not come from the New Amazon or New Magento store
    ValueError: The shipment has no shipment items associated with it
    ValueError: An item does not have a nonzero unit price or quantity ordered
  """
  shipments = requests.get(resource_url,
    headers={"Authorization": os.environ["AUTH_CREDS"]}).json()
  if shipments["total"] < 0:
    raise ValueError("There are no shipments associated with this URL")

  store_ids = get_store_ids()
  for shipment in shipments["shipments"]:
    if shipment["advancedOptions"]["storeId"] not in store_ids:
      raise ValueError("Not an Amazon or Magento order")

    items = shipment["shipmentItems"]

    if len(items) == 0:
      raise ValueError("This shipment has no shipments items associated with it")

    for item in items:
      if item["quantity"] == 0 or item["unitPrice"] == 0:
        raise ValueError("An item does not have a nonzero quantity or unit price")

def get_store_ids() -> set:
  """Gets a set of store ids for the New Magento and New Amazon stores

  Returns:
    A set of store ids for the New Magento and New Amazon stores
  """
  res = requests.get("https://ssapi.shipstation.com/stores",
    {"showInactive": "False"},
    headers={"Authorization": os.environ["AUTH_CREDS"]})

  assert res.status_code == 200, "Unable to connect to ShipStation API"

  stores = res.json()
  store_ids = set()

  for store in stores:
    if store["storeName"] == "New Amazon Store" or store["storeName"] == "New Magento Store":
      store_ids.add(store["storeId"])

  return store_ids