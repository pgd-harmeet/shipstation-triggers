import logging
import os
import azure.functions as func
import net.requester as request


def main(req: func.HttpRequest) -> func.HttpResponse:
    logging.info('Processing an order from ShipStation')
    req = req.get_json()
    resource_url = req['resource_url']
    resource_type = req['resource_type']
    
    if (resource_type != 'SHIP_NOTIFY'):
        return func.HttpResponse(f'This is not a "on items shipped" webhook', status_code=400)

    order_info = request.get(resource_url, None, headers={'Authorization': 'Basic M2I3MmUyOGI0ZWI1NDdhYjk3NmNjMGFjOGIxYTA2NjI6ZmUyYmJjNjRkN2RlNDI2YzhjMjk4YjQxMDdkYWM2MGE='})

    logging.info(order_info.json())

    return func.HttpResponse("Finished")
