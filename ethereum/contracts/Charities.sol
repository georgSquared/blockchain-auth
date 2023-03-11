// SPDX-License-Identifier: GPL-3.0

pragma solidity >=0.7.0 <0.9.0;

contract Charities {
    address public owner;
    address payable [] internal charities;
    address top_donor;

    uint total_donated;
    uint top_donation;

    uint [] valid_indices_array;

    // Intializing the state variable
    uint randNonce = 0;

    constructor (address payable [] memory _charities) {
        owner = msg.sender;
        charities = _charities;
        uint i;

        for (i = 0; i < charities.length; i++) {
            valid_indices_array.push(i);
        }
    }

    modifier onlyOwner {
        require(msg.sender == owner, "Unauthorized Use");
        _;
    }

    // Use "indexed" for logging
    event Donation(address indexed from, uint256 value);

    // A function to return random numbers bounded by modulo
    // https://www.geeksforgeeks.org/random-number-generator-in-solidity-using-keccak256/
    function randMod(uint _modulus) internal returns (uint) {
        randNonce++;
        return uint(keccak256(abi.encodePacked(block.timestamp, msg.sender, randNonce))) % _modulus;
    }

    // Return the available charity max index so callers know what indices to use
    // We do this, since we made the charities private
    function get_valid_charities() public view returns (uint [] memory) {
        return valid_indices_array;
    }

    // A very simple percentage function, can overflow
    function get_percentage(uint initial, uint percentage) internal pure
    returns (uint) {
        return initial * percentage / 100;
    }

    // Facilitate the sending of the funds
    function send_funds(address payable recipient_addr, address payable charity_addr, uint true_amount, uint charity_amount) internal {
        // Pay the charity and recipient
        (bool charity_success,) = charity_addr.call{value : charity_amount}("");
        require(charity_success, "Transfer to charity failed.");

        (bool transfer_success,) = recipient_addr.call{value : true_amount}("");
        require(transfer_success, "Transfer to recipient failed.");

        // emit donation event when transfers are made
        emit Donation(msg.sender, charity_amount);
    }

    // A simple function to update the top donation and donor
    function update_top_donation(uint new_donation) internal {
        if (new_donation > top_donation) {
            top_donation = new_donation;
            top_donor = msg.sender;
        }
    }

    function get_top_donation() public view onlyOwner
    returns (address, uint){
        return (top_donor, top_donation);
    }

    function transfer(address payable recipient, uint amount, uint charity_index) public payable {
        // Check that sender has sufficient amount
        require(msg.sender.balance >= amount, "Insufficient funds");

        // Check that the index is correct
        require(charity_index < charities.length && charity_index >= 0, "Invalid charity index");

        uint to_charity;
        uint true_amount;

        to_charity = get_percentage(amount, 10);
        true_amount = amount - to_charity;

        send_funds(recipient, charities[charity_index], true_amount, to_charity);

        // Keep track of the total amount donated
        total_donated += to_charity;

        // Update the top donation amount and donor
        update_top_donation(to_charity);
    }

    function transfer(address payable recipient, uint amount, uint charity_index, uint charity_amount) public payable {
        // Check that sender has sufficient amount
        require(msg.sender.balance >= amount, "Insufficient funds");

        // Check that the index is correct
        require(charity_index < charities.length && charity_index >= 0, "Invalid charity index");

        uint to_charity;
        uint true_amount;
        uint min_amount;
        uint max_amount;

        min_amount = get_percentage(amount, 1);
        max_amount = get_percentage(amount, 50);

        // Check that the provided amount is valid
        require(charity_amount <= max_amount && charity_amount >= min_amount);

        to_charity = get_percentage(amount, 10);
        true_amount = amount - to_charity;

        send_funds(recipient, charities[charity_index], true_amount, to_charity);

        // Keep track of the total amount donated
        total_donated += to_charity;

        // Update the top donation amount and donor
        update_top_donation(to_charity);
    }

    // destructor
    // Pick a random charity and send any funds there
    function destroy() public onlyOwner {
        uint charity_index;

        charity_index = randMod(charities.length);

        // From Solidity 0.8.0 you don't need to declare the address as payable explicitly, but when you are transferring an amount to such address
        // From: https://ethereum.stackexchange.com/questions/94707/msg-sender-not-address-payable-solidity-0-8-2
        selfdestruct(payable(charities[charity_index]));
    }
}