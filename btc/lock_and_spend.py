from bitcoinutils.constants import TYPE_ABSOLUTE_TIMELOCK
from bitcoinutils.keys import P2pkhAddress, PrivateKey
from bitcoinutils.proxy import NodeProxy
from bitcoinutils.script import Script
from bitcoinutils.setup import setup

# These are defined on bitcoin.conf and should be set accordingly for each network
from bitcoinutils.transactions import Locktime, TxInput, TxOutput, Transaction, Sequence
from bitcoinutils.utils import to_satoshis

RPCUSER = 'georg'
RPCPASSWORD = 'super_secret'


def get_user_lock_key():
    """
    Gets user input for a locktime and a private key
    :return:
    """
    locktime = input("Please provide a lock time: ")
    if not isinstance(locktime, int):
        locktime = int(locktime)

    priv_key = input("Please provide a private key: ")

    return locktime, priv_key


def get_user_p2sh():
    """
    Get user input for a P2SH that may be timelocked as instructed
    :return:
    """
    addr_from = input("Please provide a P2SH with available funds: ")
    return addr_from


def get_user_p2pkh():
    """
        Get user input for a P2SH that may be timelocked as instructed
        :return:
        """
    addr_to = input("Please provide a P2PKH to send funds to: ")
    return addr_to


def setup_node_proxy():
    """
    Setup a Node Proxy so that we can query the local bitcoin node and return the proxy
    :return:
    """
    proxy = NodeProxy(RPCUSER, RPCPASSWORD).get_proxy()
    return proxy


def check_unspent(proxy, addresses):
    if not isinstance(addresses, list):
        addresses = [addresses]

    # Query the node to get the available UTXOs for the address
    # We first need to import the address to our wallet to check
    # We practically skip filtering by specifying default min and max block confirmations
    proxy.importaddress(addresses[0])
    unspent = proxy.listunspent(1, 9999999, addresses)
    if not unspent:
        raise ValueError("Provided address has no available UTXOs")

    results = []
    for utxo in unspent:
        results.append({
            "txid": utxo['txid'],
            "vout": utxo['vout'],
            "amount": utxo['amount']
        })

    return results


def create_transaction(utxos, locktime, address, priv_key):
    """
    For every UTXO we create a transaction input and output of equal amount,
    addressed at the user provided P2PKH
    :param utxos: The UTXO relevant information
    :param locktime: The user provided locktime
    :param address: The addres to send the funds to
    :return:
    """
    # We now have to sign the transaction with the key corresponding to the input address
    # Decide whether the time given is expressed in blocks or epoch
    if int(locktime) < 500000000:
        is_type_block = True
    else:
        is_type_block = False

    # Create the sequence with the appropriate arguments
    seq = Sequence(TYPE_ABSOLUTE_TIMELOCK, locktime, is_type_block=is_type_block)
    to_addr = P2pkhAddress(address)

    inputs = []
    outputs = []
    for utx in utxos:
        txin = TxInput(utx["txid"], utx["vout"], sequence=seq.for_input_sequence())
        inputs.append(txin)

        txout = TxOutput(to_satoshis(utx['amount']), to_addr.to_script_pub_key())
        outputs.append(txout)

    tx = Transaction(inputs, outputs)

    print(f"Raw unsigned transaction: {tx.serialize()}")

    # We now have to sign the transaction with the key corresponding to the input address

    # Calculate the P2PKH corresponding to the P2SH that carries the inputs
    priv = PrivateKey(priv_key)
    pub_key = priv.get_public_key().to_hex()
    signing_addr = priv.get_public_key().get_address()

    # Create the appropriate redeem/locking script
    redeem_script = Script([seq.for_script(), 'OP_CHECKLOCKTIMEVERIFY', 'OP_DROP', 'OP_DUP',
                            'OP_HASH160', signing_addr.to_hash160(), 'OP_EQUALVERIFY', 'OP_CHECKSIG'])

    # use the private key corresponding to the address that contains the
    # UTXO we are trying to spend to create the signature for the txin -
    # note that the redeem script is passed to replace the scriptSig
    sig = priv.sign_input(tx, 0, redeem_script)

    # All inputs are created from the same address and thus can be signed with the same key
    for txin in inputs:
        txin.script_sig = Script([sig, pub_key, redeem_script.to_hex()])

    signed_tx = tx.serialize()

    print(f"Raw signed transaction: {signed_tx}")
    print(f"TxId: {tx.get_txid()}")

    return tx


def calculate_fees(proxy, tx, blocks=6, pay_fees=False):
    """
    Calculate fees based on the local Node and optionally attempt to pay them
    If the option to pay fees is selected, transaction should be re-signed since inputs may be added
    :return:
    """
    result = proxy.estimatesmartfee(blocks)
    rate = result["feerate"]

    tx_size_bytes = tx.get_size()
    fees = rate * (tx_size_bytes / 1000)
    print(f"Required fees are {fees} BTC")

    if pay_fees:
        proxy.fundrawtransaction(tx.get_hash())


def validate_tx(proxy, tx):
    result = proxy.validateaddress(tx.get_hash())
    if not result['isvalid']:
        raise ValueError("The transaction is invalid!")


def main():
    locktime, priv_key = get_user_lock_key()
    addr_from = get_user_p2sh()
    addr_to = get_user_p2pkh()

    proxy = setup_node_proxy()
    utxos = check_unspent(proxy, addr_from)

    tx = create_transaction(utxos, locktime, addr_to, priv_key)

    # We will now calculate the fees
    # Ideally we would have to recreate the transaction, subtracting the fees from the output amount
    calculate_fees(proxy, tx, pay_fees=False)

    # After some change, all transactions seem to end up invalid. I presume there has been a mistake with the
    # signing process
    validate_tx(proxy, tx)


if __name__ == "__main__":
    setup('regtest')
    main()
