from flask import Flask, request

app = Flask(__name__)

@app.route('/agent-output', methods=['POST'])
def receive_agent_output():
    data = request.json
    print("Received agent output:")
    print(data)

    return '', 200

if __name__ == '__main__':
    app.run(port=8000)