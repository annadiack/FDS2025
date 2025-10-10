    import grpc
    import dservice_pb2
    import dservice_pb2_grpc
    import hservice_pb2
    import hservice_pb2_grpc

    def run():
        # Configuration
        username = 'team fox' 
        password = 'test'   
        data_to_store = "Hello FDS FS25! This is our team's data for the gRPC exercise."
    
        # Data Server connection
        data_channel = grpc.insecure_channel('localhost:50051')
        data_stub = dservice_pb2_grpc.DBStub(data_channel)
    
        print("=== FDS FS25 - Exercise 1 Task 2 - gRPC Client ===")
    
        # Step 1: Register user
        print("\n1. Registering user...")
        user_credentials = dservice_pb2.UserPass(username=username, password=password)
        register_response = data_stub.RegisterUser(user_credentials)
    
        if register_response.success:
            print("   ✓ User registered successfully")
        else:
            print("   ✗ User registration failed (might already exist)")
    
        # Step 2: Store data
        print("\n2. Storing data...")
        store_request = dservice_pb2.StoreReq(
            username=username, 
            password=password, 
            msg=data_to_store
        )
        store_response = data_stub.StoreData(store_request)
    
        if store_response.success:
            print("   ✓ Data stored successfully")
        else:
            print("   ✗ Data storage failed - stopping execution")
            return
    
        # Step 3: Generate passcode
        print("\n3. Generating passcode...")
        passcode_response = data_stub.GenPasscode(user_credentials)
    
        if passcode_response.code:
            passcode = passcode_response.code
            print(f"   ✓ Passcode generated: {passcode}")
        else:
            print("   ✗ Passcode generation failed - stopping execution")
            return
    
        # Step 4: Get hash from Hash Server
        print("\n4. Requesting hash calculation...")
    
        # Hash Server connection
        hash_channel = grpc.insecure_channel('localhost:50052')
        hash_stub = hservice_pb2_grpc.HSStub(hash_channel)
    
        hash_request = hservice_pb2.Request(
            passcode=passcode,
            ip="127.0.0.1",
            port=50051
        )
    
        hash_response = hash_stub.GetHash(hash_request)
    
        print(f"\n=== RESULT ===")
        print(f"Original data: '{data_to_store}'")
        print(f"Calculated hash: {hash_response.hash}")
        print("===============")

    if __name__ == '__main__':
        run()