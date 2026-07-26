import json


def parse_telemetry(data):

    try:

        telemetry = json.loads(data)

        return telemetry

    except Exception as e:

        print("Telemetry Parse Error:", e)

        return None


