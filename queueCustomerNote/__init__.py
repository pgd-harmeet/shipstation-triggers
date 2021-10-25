"""
Queues an order to number to add "Sent to WSI" to customer notes
"""

import logging
import azure.functions as func

def main(req: func.HttpRequest, msg: func.Out[func.QueueMessage]) -> func.HttpResponse:
  order_num = req.params.get("orderNumber")

  if order_num:
    msg.set(order_num)
    logging.info(f"Successfully queued {order_num}")
    return func.HttpResponse(f"Successfully queued {order_num}", status_code=200)

  logging.warn(f"Could not queue {order_num}")
  return func.HttpResponse(f"Could not queue {order_num}", status_code=400)
