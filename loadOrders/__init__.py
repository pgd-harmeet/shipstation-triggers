import logging
import os
import azure.functions as func
from net.requester.requester import Requester


def main(req: func.HttpRequest) -> func.HttpResponse:
    logging.info('Processing an order from ShipStation')
    resource_url = req.params['resource_url']
    resource_type = req.params['resource_type']

    print(resource_url, resource_type)

    if (resource_type != 'SHIP_NOTIFY'):
        return func.HttpResponse(f'This is not a "on items shipped" webhook', status_code=400)

    shipstation_requester = Requester('https://ssapi.shipstation.com', 'ssapi.shipstation.com')
    shipstation_requester.encode_base64(os.environ['SS_KEY'], os.environ['SS_SECRET_KEY'])

    order_info = shipstation_requester.get(resource_url)

    return func.HttpResponse(order_info)
