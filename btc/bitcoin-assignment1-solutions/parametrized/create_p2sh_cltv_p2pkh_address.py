#!/usr/bin/env python
# vim:et:sta:sts=4:sw=4:ts=8:tw=79:

# Copyright (C) 2019 The python-bitcoin-utils developers
#
# This file is part of python-bitcoin-utils
#
# It is subject to the license terms in the LICENSE file found in the
# top-level directory of this distribution.
#
# No part of python-bitcoin-utils, including this file, may be copied,
# modified, propagated, or distributed except according to the terms
# contained in the LICENSE file.

# Usage example:
# ./create_p2sh_cltv_p2pkh_address.py --priv cSbKZh6a6wNUAQ8pr2KLKeZCQ4eJnFmN35wtReaoU4kCP97XQu6W --time 650
# ./create_p2sh_cltv_p2pkh_address.py --pub 03554e207b068e4116b2028d02d0ee8ac5cda38f86896e9deb15c8f85c44a8f29c --time 650
#
# Show help message with:
# ./create_p2sh_cltv_p2pkh_address.py --help

import binascii
import click
import sys
from bitcoinutils.setup import setup
from bitcoinutils.transactions import Transaction, TxInput, TxOutput, Sequence
from bitcoinutils.keys import P2pkhAddress, P2shAddress, PrivateKey, PublicKey
from bitcoinutils.script import Script
from bitcoinutils.constants import TYPE_ABSOLUTE_TIMELOCK

@click.command()
@click.option("--pub", help="Public key")
@click.option("--priv", help="Private key")
@click.option("--time", help="Unlock time (block height or unix epoch)",
        type=int)

def main(pub, priv, time):

    # always remember to setup the network
    setup('regtest')

    #
    # This script creates a P2SH address containing a
    # CHECKLOCKTIMEVERIFY plus a P2PKH locking funds with a key
    # until a certain block_height is reached
    #

    # set unlocking time
    if not time:
        print("ERROR: You have to set the unlocking time using the --time "
                "option.")
        sys.exit(1)

    seq = Sequence(TYPE_ABSOLUTE_TIMELOCK, time)

    # secret/public key needed for the P2SH (P2PKH) transaction
    if priv:
        # if the user has entered a private key, use that to calculate the
        # public key
        p2pkh_sk = PrivateKey(priv)
        p2pkh_pk = p2pkh_sk.get_public_key()
    elif pub:
        # if the user has entered a public key, use that directly
        p2pkh_pk = PublicKey(pub)
    else:
        print("ERROR: You have to set either a public key or a private "
                "key using the --pub or --priv options")
        sys.exit(1)

    # get the address (from the public key)
    p2pkh_addr = p2pkh_pk.get_address()

    # create the redeem script
    redeem_script = Script([seq.for_script(), 'OP_CHECKLOCKTIMEVERIFY', 'OP_DROP', 'OP_DUP', 'OP_HASH160', p2pkh_addr.to_hash160(), 'OP_EQUALVERIFY', 'OP_CHECKSIG'])

    # create a P2SH address from a redeem script
    addr = P2shAddress.from_script(redeem_script)
    print(addr.to_string())

if __name__ == "__main__":
    main()

