# Architecture

QuantCore is divided into logical layers.

1. Data Providers
2. Data Storage
3. C++ Computational Core
4. Python Research Layer
5. FastAPI Routers
6. Dashboard/UI

The separation allows independent development of research, execution, and presentation while reducing coupling.

Typical workflow:

Market Data
 -> Storage
 -> Feature Generation
 -> Strategy
 -> Risk
 -> Execution/Paper Broker
 -> Dashboard/API
