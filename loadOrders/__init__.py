import logging
import os
import azure.functions as func
import net.requester as request
import datetime
import re


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

def generate_order_sheet(order_info):
    order_data = order_info['shipments'][0]

    header = _generate_header(order_data)

    print(header)


def _generate_header(order_info):
    # Initialize header
    header = 'H'

    date = datetime.datetime.fromisoformat(order_info['createDate'][:-1])

    # Add date and time to header
    header += date.strftime('%m%d%Y%H%M%S')
    # Store number
    header += '1'
    # Default Epicor customer ID
    header += '145050'
    # Customer job number, set to default Eagle value
    header += '0' * 3

    # TODO: Add tax code
    header += 'ZZZ'

    # TODO: Add tax rate
    header += '0' * 5

    # Pricing indicator and percentage
    header += 'R0000'
    # Eagle Clerk ID
    header += 'EComm     '
    # Customer PO Number
    header += ' ' * 12
    # Transaction total
    header += '0' * 9 + '+'
    # Sale taxable
    header += 'Y'
    # Sales person number
    header += ' ' * 2

    # TODO: Add sales tax
    header += '0' * 9 + '+'

    # Always blank lines
    header += ' ' * 10

    # TODO: Instructions 1
    header += ' ' * 30

    # TODO: Instructions 2
    header += ' ' * 30

    # Ship-To Name
    ship_to_name = order_info['shipTo']['name']
    header += ship_to_name + ' ' * (30 - len(ship_to_name))
    # Ship-To Address 1
    ship_to_addr_1 = order_info['shipTo']['street1']
    header += ship_to_addr_1 + ' ' * (30 - len(ship_to_addr_1))
    # Ship-To Address 2
    ship_to_addr_2 = order_info['shipTo']['street2']
    header += ship_to_addr_2 + ' ' * (30 - len(ship_to_addr_2))
    # Ship-To Address 3
    ship_to_addr_3 = order_info['shipTo']['city'] + ' ' + \
        order_info['shipTo']['state'] + ' ' + \
        order_info['shipTo']['postalCode']
    header += ship_to_addr_3 + ' ' * (30 - len(ship_to_addr_3))

    # Reference Information
    header += ' ' * 30
    # Customer Telephone
    telephone = order_info['shipTo']['phone']
    tele_normalized = re.sub(r'\s+|-|(\+\d)|(ext\..+)', '', telephone)
    header += tele_normalized + ' ' * (10 - len(tele_normalized))
    # Customer resale no., customer ID, special order vendor
    header += ' ' * 34
    # Total deposit
    total_deposit = 0
    for item in order_info['shipmentItems']:
        total_deposit += item['unitPrice']
    header += normalize_value(total_deposit)

    # Expected & expiration date
    header += '0' * 16

    # Terminal number
    header += '0' * 3

    # TODO Transaction number
    header += '0' * 8

    # TODO Transaction Type
    header += '1'

    # Total cash tendered
    header += '0' * 9 + '+'
    # Charge Tendered
    header += '0' * 9 + '+'
    # Change given
    header += '0' * 9 + '+'
    # Total check tendered
    header += '0' * 9 + '+'
    # Check number
    header += '0' * 6
    # Bankcard tendered
    header += normalize_value(total_deposit)

    # TODO Bankcard number
    header += ' ' * 16

    # Apply-To Number & Third Party Vendor Code
    header += ' ' * 8

    # Use ESTU cost indicator
    header += 'N'

    # Private label card type, special transaction processing flag,
    # private label card promo type, tdx transaction, *unused*
    header += ' ' * 8

    # Direct ship
    header += 'N'

    # Rest of document
    header += ' ' * 6

    return header

def normalize_value(value):
    """
    Normalizes monetary value so that it conforms to Eagle's 9(7)v9(2) +/- format
    :param value: Value to be normalized
    :return: Normalized value
    """
    value = int(value * 100)
    return '0' * (9 - len(str(value))) + str(value) + '+'
