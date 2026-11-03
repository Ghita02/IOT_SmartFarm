\# Digital Twin Layer



The Digital Twin layer represents and manages the Smart Farm as a digital

system.



The SmartFarmDigitalTwin class coordinates the Digital Replicas representing

the physical sensors and irrigation relay.



Responsibilities:



\- Maintain the identity of the Smart Farm Digital Twin.

\- Coordinate the Digital Replica manager.

\- Process incoming sensor measurements.

\- Process actuator status updates.

\- Provide the current digital state of the Smart Farm.



The Digital Twin receives updates from the MQTT subscriber through the

services layer.



Its state can be retrieved through the Flask endpoint:



`GET /api/digital-twin`



Implementation: `core.py`.

