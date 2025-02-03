from tortoise import Tortoise, run_async

async def run():
    await Tortoise.init(
        db_url="mysql://admin:admin@localhost:3306/rfid", modules={"models": ["models"]}
    )
    await Tortoise.generate_schemas(safe=True)


if __name__ == "__main__":
    run_async(run())
