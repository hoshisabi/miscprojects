#!/usr/bin/env python3
import os, pathlib, time
from dotenv import load_dotenv
load_dotenv(pathlib.Path(__file__).parent / ".env")
from google import genai
from google.genai import types

client = genai.Client(api_key=os.environ["GOOGLE_KEY"])

out_path = pathlib.Path(__file__).parent.parent.parent / "hoshisabi.github.io" / "rpg" / "icewind-dale" / "wiki" / "characters" / "npcs" / "images" / "old-goat.png"

prompt = (
    "An elderly female Goliath humanoid chieftain, Goliaths are large grey-blue skinned humanoids "
    "resembling giant humans with mottled stone-like skin markings, deeply lined face full of wisdom "
    "and hard-won authority, smoking a pipe, wearing tribal elder's furs and jewelry, "
    "sharp piercing eyes that miss nothing, her nickname is Old Goat but she is a person not an animal, "
    "arctic Icewind Dale setting, D&D fantasy character portrait, painterly style, dramatic lighting, no text"
)

print("Regenerating Old Goat portrait...")
response = client.models.generate_images(
    model="imagen-4.0-fast-generate-001",
    prompt=prompt,
    config=types.GenerateImagesConfig(number_of_images=1),
)
response.generated_images[0].image.save(out_path)
print(f"Saved {out_path}")
