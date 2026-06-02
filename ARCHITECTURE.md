# Smart Engine Architecture

Smart Engine is a small **event-driven notification system**.

It listens for donation-related events, understands what they mean, finds users who may care, and publishes notification commands for them.

## Main parts

### 2) Worker
A background process that listens to Redis Pub/Sub messages.
It receives events and sends them through the processing pipeline.

### 3) Redis
Redis is used for two jobs:
- **event transport**: passing events between services
- **storage**: keeping user and donation vector data for matching

### 4) Embeddings service
This service turns text into vectors.
It sends text to an external embedding model and gets back numeric representations that are easier for the system to compare.

### 5) Vector store
This part stores vectors in Redis Stack and searches them.
It helps the system find users whose interests are close to a new donation.

### 6) Notification publisher
When a match is found, this service publishes a notification command back to Redis.
Another service can later consume that command and deliver the actual notification.

## How the flow works

1. Another service publishes an event to Redis.
2. The worker receives the event.
3. The event is validated with Pydantic models.
4. Text is built from the event data.
5. The text is converted into an embedding.
6. The embedding is saved in Redis.
7. The system searches for matching users.
8. If users match, notification commands are published.

## Event types

- **DonationPublished**: a new donation is available, so the system looks for interested users.
- **BeneficiarySearchPerformed**: a user search is used to update the user profile vector.
- **DonationLiked**: a user action is used to update behavior data and improve future matching.

## Why this design is simple

- The API stays small and easy to run.
- The worker can process events in the background.
- Redis keeps the setup lightweight for development.
- The system can grow later with better ranking, more event types, or a stronger database.

## Local setup

The project is designed to run with Docker Compose:

- `redis` runs Redis Stack
- `app` runs the FastAPI API
- `worker` runs the background matching process

## In one sentence

Smart Engine takes event data, turns it into vectors, matches it to people who may care, and publishes notifications.
