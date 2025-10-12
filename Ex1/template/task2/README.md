# FDS Exercise 1 – Task 2: gRPC – Data and Hash Server

### Author  
Anna Aïssatou Diack  

---

## Overview

This part of the exercise implements the Python side of the gRPC system described in Task 2.  
It contains two scripts:

- **`server.py`** – a Hash Server that provides the `GetHash()` RPC.  
- **`client.py`** – a simple client that interacts with both the Node.js Data Server and the Python Hash Server.

All services follow the `.proto` definitions provided in the exercise (`dservice.proto` and `hservice.proto`).  
The Node.js Data Server runs on **port 50051**, while the Hash Server listens on **port 50052**.

---

## 1. Running the Data Server (given code)

```bash
cd dataServer
npm install @grpc/grpc-js @grpc/proto-loader
node dataServer.js
