// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

// Stores audit-log hashes on-chain.
// Only 32-byte hashes are stored, never patient data or full records.
contract AuditAnchor {
    address public owner;                 // wallet allowed to anchor hashes
    uint256 public count;                 // number of hashes anchored so far
    mapping(uint256 => bytes32) public hashes;   // id => hash

    event HashAnchored(
        uint256 indexed id,
        bytes32 hash,
        address indexed sender,
        uint256 timestamp
    );

    constructor() {
        owner = msg.sender;               // the deploying wallet becomes the owner
    }

    // Only the owner wallet (your system) can anchor a hash
    function anchor(bytes32 h) external returns (uint256) {
        require(msg.sender == owner, "not authorised");
        count++;
        hashes[count] = h;
        emit HashAnchored(count, h, msg.sender, block.timestamp);
        return count;
    }
}
