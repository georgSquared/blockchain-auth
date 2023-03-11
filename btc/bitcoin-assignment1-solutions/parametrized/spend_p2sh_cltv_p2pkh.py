#!/usr/bin/env python
# vim:et:sta:sts=4:sw=4:ts=8:tw=79:

# Copyright (C) 2019 The python-bitcoin-utils developers
#
# This file is part of python-bitcoin-utils
#
# It is subject to the license terms in the LICENSE file found in the top-level
# directory of this distribution.
#
# No part of python-bitcoin-utils, including this file, may be copied,
# modified, propagated, or distributed except according to the terms contained
# in the LICENSE file.

#
# This script spends all available funds that a P2SH address containing a
# CLTV+P2PKH script as created from examples/create_p2sh_cltv_p2pkh.py has
# received
#
#
# Usage example:
# ./spend_p2sh_cltv_p2pkh.py \
#   --priv cSbKZh6a6wNUAQ8pr2KLKeZCQ4eJnFmN35wtReaoU4kCP97XQu6W \
#   --time 650 \
#   --p2sh 2NDSLmcdfvk8XjyihwqeR5wNoaKT9iujjr4 \
#   --p2pkh mhGCmMqy9NKCRB5idDHW5jHsHsjSRWCQs5 \
#   --rpcuser rpcuser \
#   --rpcpass rpcpass
#
# Show help message with
# ./spend_p2sh_cltv_p2pkh.py --help

# Make sure you have a regtest section in your bitcoin.conf with the following
# parameters set (you may change the actual values):
# [regtest]
# maxtxfee=20
# fallbackfee=2

from bitcoinutils.transactions import Transaction, TxInput, TxOutput, Sequence, Locktime
from bitcoinutils.keys import P2pkhAddress, P2shAddress, PrivateKey
from bitcoinutils.constants import TYPE_ABSOLUTE_TIMELOCK
from bitcoinutils.utils import to_satoshis
from bitcoinutils.proxy import NodeProxy
from bitcoinutils.script import Script
from bitcoinutils.setup import setup
import requests
import click
import sys

@click.command()
@click.option("--priv", help="Private key for the P2PKH part")
@click.option("--time", help="Unlock time (block height or unix epoch)",
        type=int)
@click.option("--p2sh", help="The P2SH address to get the funds from")
@click.option("--p2pkh", help="The P2PKH address to send the funds to")
@click.option("--rpcuser", help="RPC proxy username")
@click.option("--rpcpass", help="RPC proxy password")

def main(priv, time, p2sh, p2pkh, rpcuser, rpcpass):

    # always remember to setup the network
    setup('regtest')

    # RPC credentials for communicating with the node
    if not rpcuser or not rpcpass:
        print("ERROR: You have to provide RPC user and password using the "
                "--rpcuser and --rpcpass options.")
        sys.exit(1)
    proxy = NodeProxy(rpcuser, rpcpass).get_proxy()

    # set unlocking time
    if not time:
        print("ERROR: You have to set the unlocking time using the --time "
                "option.")
        sys.exit(1)
    
    seq = Sequence(TYPE_ABSOLUTE_TIMELOCK, time)
    lock = Locktime(time)

    # secret key needed to spend P2PKH that is wrapped by P2SH
    if priv:
        p2pkh_sk = PrivateKey(priv)
    else:
        print("ERROR: You have to provide a private key using the "
                "--priv option.")
        sys.exit(1)
    # this is the P2SH address the funds have been locked in
    if not p2sh:
        print("ERROR: You have to provide a P2SH address using the "
                "--p2sh option.")
        sys.exit(1)
    # this is the address the funds will be sent to 
    if not p2pkh:
        print("ERROR: You have to provide a P2PKH address using the "
                "--p2pkh option.")
        sys.exit(1)
    to_addr = P2pkhAddress(p2pkh)


    # import the address as watch-only
    proxy.importaddress(p2sh , "P2SH absolute timelock", True)
    # find all UTXOs for this address. 10.000.000 should be enough
    list_unspent = proxy.listunspent(0, 9999999, [p2sh])

    # create transaction inputs for all UTXOs. Calculate the total amount of
    # bitcoins they contain
    txin_list = []
    total_amount = 0
    for i in list_unspent:
        txin = TxInput(i['txid'], i['vout'], sequence=seq.for_input_sequence())
        txin_list.append(txin)
        total_amount = total_amount + to_satoshis(i['amount'])
    if total_amount == 0:
        print("No funds to move")
        sys.exit(0)
    print("Total funds to move (satoshis): ", total_amount)

    # derive public key and adddress from the private key
    p2pkh_pk = p2pkh_sk.get_public_key().to_hex()
    p2pkh_addr = p2pkh_sk.get_public_key().get_address()

    # create the redeem script - needed to sign the transaction
    redeem_script = Script([seq.for_script(), 'OP_CHECKLOCKTIMEVERIFY', 'OP_DROP', 'OP_DUP', 'OP_HASH160', p2pkh_addr.to_hash160(), 'OP_EQUALVERIFY', 'OP_CHECKSIG'])

    # get fees using API. Although we may be running in regtest, we'll use the
    # fees as if we were using testnet (fees are in satoshis)
    url = 'https://api.blockcypher.com/v1/btc/test3'
    resp = requests.get(url)
    fee_per_kb = resp.json()['medium_fee_per_kb']

    # calculate transaction size according to:
    # in*180 + out*34 + 10 plus or minus 'in'
    # https://bitcoin.stackexchange.com/questions/1195/how-to-calculate-transaction-size-before-sending-legacy-non-segwit-p2pkh-p2sh
    # we'll play it safe and use the upper bound
    tx_size = len(txin_list) * 180 + 34 + 10 + len(txin_list)
    fees = to_satoshis(tx_size * fee_per_kb / (1024 * 10**8))
    print('fees (satoshis):', fees)

    # create the output
    txout = TxOutput(total_amount - fees, to_addr.to_script_pub_key() )

    # create transaction from inputs/outputs
    tx = Transaction(txin_list, [txout], lock.for_transaction())


    # use the private key corresponding to the address that contains the
    # UTXO we are trying to spend to create the signatures for all txins -
    # note that the redeem script is passed to replace the scriptSig
    for i, txin in enumerate(txin_list):
        sig = p2pkh_sk.sign_input(tx, i, redeem_script )
        # set the scriptSig (unlocking script) -- unlock the P2PKH (sig, pk)
        # plus the redeem script, since it is a P2SH
        txin.script_sig = Script([sig, p2pkh_pk, redeem_script.to_hex()])

    # serialize the transaction
    signed_tx = tx.serialize()
    
    # test if the transaction will be accepted by the mempool
    res = proxy.testmempoolaccept([signed_tx])
    if not res[0]['allowed']:
        print("Transaction not valid")
        sys.exit(1)

    # print raw transaction
    print("\nRaw unsigned transaction:\n" + tx.serialize())
    # print raw signed transaction ready to be broadcasted
    print("\nRaw signed transaction:\n" + signed_tx)
    print("\nTxId:", tx.get_txid())

    # send transactions
    print("\nSending transaction...\n")
    proxy.sendrawtransaction(signed_tx)

if __name__ == "__main__":
    main()

