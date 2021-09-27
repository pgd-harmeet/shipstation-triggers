import logging
import os
import azure.functions as func
from azure.storage.blob.aio import ContainerClient
from azure.core.exceptions import ResourceExistsError
import datetime
import re
import requests

async def main(req: func.HttpRequest) -> func.HttpResponse:
    try:
        req = req.get_json()
        resource_url = req['resource_url']
        resource_type = req['resource_type']
        logging.info(f'RESOURCE URL: ${resource_url}')
    except (ValueError, KeyError):
        logging.error('No JSON body or "resource_url" and "resource_type" keys not present')
        return func.HttpResponse('Please submit a JSON body with your request with keys "resource_url" and "resource_type"', status_code=400)

    if (resource_type != 'SHIP_NOTIFY'):
        logging.error('Request is not for an "on items shipped webhook"')
        return func.HttpResponse('This is not an "on items shipped" webhook', status_code=400)

    # Makes the response include items that were shipped with that order
    resource_url = resource_url.replace('includeShipmentItems=False', 'includeShipmentItems=True')
    order_info = requests.get(resource_url, None, headers={'Authorization': os.environ['AUTH_CREDS']}).json()

    try:
        logging.info(f'Creating an order sheet for {order_info["shipments"][0]["orderKey"]}')
        order_sheet = generate_order_sheet(order_info)
    except IndexError as e:
        logging.info('The batch ID for this resource_url has no shipments associated with it')
        return func.HttpResponse('The batch ID for this resource_url has no shipments associated with it', status_code=422)
    except ValueError as e:
        # Order contains items with either a quantity ordered or unit price that is <= 0, usually for replacement orders
        logging.info(str(e))
        return func.HttpResponse(str(e), status_code=400)

    today = datetime.date.today().strftime('%m-%d-%Y')
    container = ContainerClient.from_connection_string(conn_str=os.environ['AzureWebJobsStorage'], container_name='eagle-' + today)
    if not await container.exists():
        await container.create_container()

    # Upload and close container
    try:
        await container.upload_blob(name='EagleOrder_M' + str(order_info['shipments'][0]['orderId']) + 'O.txt', data=order_sheet)
    except ResourceExistsError:
        logging.warning(f'Order sheet for {order_info["shipments"][0]["orderKey"]} already exists')
        return func.HttpResponse(f'Order sheet for {order_info["shipments"][0]["orderKey"]} already exists', status_code=400)
    await container.close()

    logging.info(f'Successfully created Eagle order sheet for {order_info["shipments"][0]["orderKey"]}')
    return func.HttpResponse(f'Successfully created Eagle order sheet for {order_info["shipments"][0]["orderKey"]}', status_code=200)

def generate_order_sheet(order: dict)-> str:
    """
    Generates an order sheet

    :param order: dict containing a set of orders for a batch ID
    :return: str that contains order information in Eagle format
    """
    order_data = order['shipments'][0]

    header = _generate_header(order_data)
    details = _generate_details(order_data)

    return header + '\n' + details

def _generate_header(order_info: dict) -> str:
    """
    Generates a header entry for an order

    :param order_info: dict containing information for a singular order
    :raise ValueError: Quantity ordered or the unit price of an item is <= 0, usually happens for replacement orders
    :return: str containing header details for an Eagle order
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

    # MTX tax code
    header += ' ' * 3

    # Tax rate charged
    tax_amount = order_info['shipmentItems'][0]['taxAmount'] or 0
    unit_price = order_info['shipmentItems'][0]['unitPrice']
    quantity_ordered = order_info['shipmentItems'][0]['quantity']
    logging.info(f'{tax_amount}, {unit_price}, {quantity_ordered}')

    try:
        tax_rate = tax_amount / quantity_ordered / unit_price
    except ZeroDivisionError:
        raise ValueError('Quantity ordered or unit price is not a number greater than 0')
    header += normalize_value(tax_rate, 0, 5, signed=False)

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

    # Add sales tax
    order_num = order_info['orderNumber']
    if re.match(r'.+-.+-.+', order_num) or re.match(r'5.+', order_num):
        header += '0' * 9 + '+'
    else:
        subtotal = 0
        tax_total = 0
        for item in order_info['shipmentItems']:
            item_tax = item['taxAmount']
            subtotal += item['unitPrice']
            if item_tax is not None:
                tax_total += item['taxAmount']
            else:
                tax_total += 0

        total_sales_tax = 1000 * (tax_total / (subtotal + order_info['shipmentCost']))

        header += normalize_value(total_sales_tax, 7, 2)

    # Always blank lines
    header += ' ' * 10

    # TODO: Instructions 1
    header += ' ' * 30

    # Instructions 2
    header += order_num + ' ' * (30 - len(order_num))

    # Ship-To Name
    ship_to_name = order_info['shipTo']['name']
    header += ship_to_name + ' ' * (30 - len(ship_to_name))
    # Ship-To Address 1
    ship_to_addr_1 = order_info['shipTo']['street1']
    header += ship_to_addr_1 + ' ' * (30 - len(ship_to_addr_1))
    # Ship-To Address 2
    ship_to_addr_2 = order_info['shipTo']['street2'] or ''
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
    header += tele_normalized[-10:] + ' ' * (10 - len(tele_normalized[-10:]))
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

    # Transaction Type
    # 1 for "Cash Sale"
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

def _generate_details(order_info: dict) -> str:
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

def normalize_value(value: float, integar_part: int, frac_part: int, signed=True) -> str:
    """
    Normalizes a numeric value so that it conforms to Eagle's number formatting
    system wherein the number of spots before and after an implied decimal are given
    Returns a signed number by default

    9 indicates an integer value from 0-9
    v is the implied decimal spot

    For a given value $112.40:
    9(4)v9(3) (4 integers -> implied decimal -> 3 integers) gives 0112400
    9(4)v9(3)+ (4 integers -> implied decimal -> 3 integers -> +) gives 011240+
    9(5)v9(3) (5 integers -> implied decimal -> 3 integers) gives 00112400


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

    value = str(int(value * 10 ** frac_part))
    field_length = integar_part + frac_part
    value = str(value) + '0' * (frac_part - 2)
    return '0' * (field_length - len(value)) + value + sign
