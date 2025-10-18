import grpc
import hservice_pb2
import hservice_pb2_grpc
import dservice_pb2
import dservice_pb2_grpc
import hashlib
from concurrent import futures

class HashServicer(hservice_pb2_grpc.HSServicer):
    def GetHash(self, request, context):
        print(f"Received hash request with passcode: {request.passcode}")

        try:
            # Connect to Data Server using provided IP and port
            channel = grpc.insecure_channel(f"{request.ip}:{request.port}")
            stub = dservice_pb2_grpc.DBStub(channel)

            # Get user data from Data Server using passcode
            passcode_msg = dservice_pb2.Passcode(code=request.passcode)
            data_response = stub.GetAuthData(passcode_msg)

            if not data_response.msg:
                return hservice_pb2.Response(hash="ERROR: Invalid passcode or no data")

            # Calculate SHA-256 hash of the data
            data_hash = hashlib.sha256(data_response.msg.encode()).hexdigest()
            print(f"Data retrieved: '{data_response.msg}' -> Hash: {data_hash}")

            return hservice_pb2.Response(hash=data_hash)

        except Exception as e:
            print(f"Error in GetHash: {e}")
            return hservice_pb2.Response(hash=f"ERROR: {str(e)}")

def serve():
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    hservice_pb2_grpc.add_HSServicer_to_server(HashServicer(), server)
    server.add_insecure_port('[::]:50052')
    print("Hash Server listening on port 50052")
    server.start()
    server.wait_for_termination()

if __name__ == '__main__':
    serve()