from bitcoinutils.constants import TYPE_ABSOLUTE_TIMELOCK
from bitcoinutils.keys import PublicKey, PrivateKey, P2shAddress
from bitcoinutils.script import Script
from bitcoinutils.setup import setup
from bitcoinutils.transactions import Sequence


# TODO validate user input and re-enter if invalid
def get_user_input():
    pub_key = input("Please provide a public key (leave blank if you would rather provide a private key): ")

    if not pub_key:
        priv_key = input("Please provide a private key: ")
    else:
        priv_key = None

    locktime = input("Please provide a lock time: ")

    return pub_key, priv_key, locktime


def main():
    # We are running locally on regtest, so set that up
    setup('regtest')

    pub, priv, time = get_user_input()

    # If a public key is provided we generate the p2pkh address directly
    # Else we first generate our pub key from the private key and then the p2pkh address
    if pub:
        pub_key = PublicKey(pub)
        address = pub_key.get_address()
    elif priv:
        priv_key = PrivateKey(priv)
        address = priv_key.get_public_key().get_address()
    else:
        raise ValueError("A public or private key must be provided!")

    # Decide whether the time given is expressed in blocks or epoch
    if int(time) < 500000000:
        is_type_block = True
    else:
        is_type_block = False

    # Create the sequence with the appropriate arguments
    seq = Sequence(TYPE_ABSOLUTE_TIMELOCK, time, is_type_block=is_type_block)

    # Create the appropriate redeem/locking script
    redeem_script = Script([seq.for_script(), 'OP_CHECKLOCKTIMEVERIFY', 'OP_DROP', 'OP_DUP',
                            'OP_HASH160', address.to_hash160(), 'OP_EQUALVERIFY', 'OP_CHECKSIG'])

    # create a P2SH address from a redeem script
    addr = P2shAddress.from_script(redeem_script)
    print(f"P2SH: {addr.to_string()}")


if __name__ == "__main__":
    main()
