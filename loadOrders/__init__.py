import logging
import os
import azure.functions as func
import net.requester as request
import datetime


def main(req: func.HttpRequest) -> func.HttpResponse:
    logging.info('Processing an order from ShipStation')
    req = req.get_json()
    resource_url = req['resource_url']
    resource_type = req['resource_type']
    
    if (resource_type != 'SHIP_NOTIFY'):
        return func.HttpResponse(f'This is not a "on items shipped" webhook', status_code=400)
    
    resource_url = resource_url.replace('includeShipmentItems=False', 'includeShipmentItems=True')
    order_info = request.get(resource_url, None, headers={'Authorization': os.environ['AUTH_CREDS']})
    order_info = order_info.json()

    return func.HttpResponse(f"Order sheet for order {order_info['shipments'][0]['orderKey']}")
