import logging
import os
import azure.functions as func
from azure.storage.blob.aio import BlobClient
import datetime
import re
import requests

async def main(req: func.HttpRequest):
    logging.info('Processing an order from ShipStation')
    try:
        req = req.get_json()
        resource_url = req['resource_url']
        resource_type = req['resource_type']
    except (ValueError, KeyError):
        return func.HttpResponse('Please submit a JSON body with your request with keys "resource_url" and "resource_type"', status_code=400)

    if (resource_type != 'SHIP_NOTIFY'):
        return func.HttpResponse(f'This is not an "on items shipped" webhook', status_code=400)

    # Makes the response include items that were shipped with that order
    resource_url = resource_url.replace('includeShipmentItems=False', 'includeShipmentItems=True')
    order_info = requests.get(resource_url, None, headers={'Authorization': os.environ['AUTH_CREDS']})
    order_info = order_info.json()
    order_sheet = generate_order_sheet(order_info)

    blob = BlobClient.from_connection_string(conn_str=os.environ['AzureWebJobsStorage'],
        container_name='eagle-orders',
        blob_name=str(order_info['shipments'][0]['orderId']) + '.txt')

    await blob.upload_blob(order_sheet)
    await blob.close()

    return func.HttpResponse('Successfully created Eagle order sheet')

def generate_order_sheet(order):
    order_data = order['shipments'][0]

    header = _generate_header(order_data)
    details = _generate_details(order_data)

    return header + '\n' + details

def _generate_header(order_info):
    """
    Generates a header entry for an order
    """
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
    header += normalize_value(total_deposit, 7, 2)

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
    header += normalize_value(total_deposit, 7, 2)

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

def _generate_details(order_info):
    """
    Generates a detail entry for each item in the order
    """
    detail = ''

    for item in order_info['shipmentItems']:
        detail += 'D'

        # Sku
        detail += item['sku'] + ' ' * (14 - len(item['sku']))

        # Item transaction type (space for sale)
        detail += ' '

        # Item description (blank for IMU description)
        detail += ' ' * 32

        # Taxable?
        detail += 'Y'

        # Pricing flag, manual price, estimate use code, trade discount,
        # discount percent, special order vendor, unit of measure
        detail += ' ' * 16

        # Quantity
        detail += normalize_value(item['quantity'], 5, 3, signed=False)

        # Unit price
        detail += normalize_value(item['unitPrice'], 5, 3, signed=False)

        # Extended Price
        detail += normalize_value(item['quantity'] * item['unitPrice'], 6, 2, signed=False)

        # Unit cost, imported from Eagle automatically
        detail += ' ' * 8

        # BOM sku, reference number, extended taxable, extended non-taxable
        # backorder quantity, unused, terms discount, direct ship, unused, filler
        detail += ' ' * 384 + '\n'

    return detail

def normalize_value(value, integar_part, frac_part, signed=True):
    """
    Normalizes monetary value so that it conforms to Eagle's number formatting
    system wherein the number of spots before and after an implied decimal are given
    Returns a signed number by default

    v is the implied decimal spot

    For a given value $112.40:
    9(4)v9(3) gives 0112400
    9(4)v9(3)+ gives 011240+
    9(5)v9(3) gives 00112400


    :param value: Value to be normalized
    :param integar_part: Number of values to the left of the implied decimal
    :param frac_part: Number of values to the right of the implied decimal
    :param signed: Whether or not the returned value is a signed number
    :return: Normalized value
    """
    sign = ''

    if signed:
        if value < 0:
            sign = '-'
        else :
            sign = '+'
    value = int(value * 100)
    value = str(value) + '0' * (frac_part - 2)
    return '0' * ((integar_part + frac_part) - len(value)) + value + sign
