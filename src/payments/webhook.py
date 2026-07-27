from fastapi import FastAPI, Request

app = FastAPI()


@app.post("/webhook/yookassa")
async def yookassa_webhook(request: Request):
    data = await request.json()

    if data.get("event") == "payment.succeeded":
        metadata = data["object"]["metadata"]
        user_id = int(metadata["user_id"])
        service_id = int(metadata["service_id"])
        payment_id = data["object"]["id"]

        # await PurchaseRepository.update_status(payment_id, "paid")

        # await bot.send_message(
        #     chat_id=user_id,
        #     text="✅ Оплата прошла успешно!"
        # )

    return {"status": "ok"}