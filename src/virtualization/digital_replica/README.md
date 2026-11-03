\# Digital Replica Layer



The Digital Replica layer provides virtual representations of the physical

sensors and actuator installed in the Smart Farm.



Each replica represents one physical component and maintains:



\- Component identity

\- Component type (sensor or actuator)

\- Latest measurement or state

\- Measurement unit

\- Last update timestamp

\- Availability status



The system includes replicas for:



\- Temperature sensor (DHT11)

\- Humidity sensor (DHT11)

\- Soil moisture sensor

\- Light sensor (LDR)

\- Irrigation relay



The DigitalReplicaManager creates and manages these replicas.



Sensor measurements received through MQTT update the corresponding

Digital Replica.



The relay replica is updated when the ESP8266 publishes its relay status.



Implementation: `replica.py`.

