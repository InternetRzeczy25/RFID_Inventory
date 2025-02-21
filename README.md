# Krzysztof Keonnowicz

System do monitorowania i zarządzania urządzeniami RFID Keonn.


## Running

Remember to <b>create a proper .env file or set the reqiured evironment variables in the terminal</b>.

Seeding the database:
```
uv run python -m server.mock.seeder
```

Running the application:
```
uv run backend.py
```

MQTT broker has to be running on localhost with provided [config](tools/mosquitto.conf)! 

One way to achieve that is to run the `MQTT server` task in VSCode. To run go to `Terminal->Run Task...`