## Demo game script. Plain, harmless text on purpose: it shows tags, variables,
## menus, input prompts and screen text, which are the things the tool must preserve.

define e = Character("Eileen", color="#c8ffc8")
define m = Character("Marcus", color="#c8c8ff")
define narrator_name = "Narrator"

default player_name = "Alex"
default coins = 3

screen coin_counter():
    frame:
        xalign 1.0
        yalign 0.0
        text "Coins: [coins]"

screen help_hint():
    frame:
        xalign 0.0
        yalign 1.0
        # These two texts are NOT marked with _(): the "unmarked texts" step finds them.
        text "Click to continue"
        textbutton "Open the diary" action NullAction()

label start:
    show screen coin_counter

    scene black
    "The morning bell rang across the quiet village."
    "A new day was beginning, and nobody knew how long it would last."

    $ player_name = renpy.input("What is your name?", default="Alex")
    $ player_name = player_name.strip() or "Alex"

    e "Good morning, [player_name]! {i}You look ready for an adventure.{/i}"
    m "Careful, Eileen. Last time you said that, we ended up lost in the woods."
    e "That was {b}one{/b} time! And we found the old bridge, remember?"
    m "We found it after three hours of walking in circles."

    menu:
        e "So, where do we go first?"

        "To the market":
            jump market
        "To the old bridge":
            jump bridge
        "Stay home":
            jump home

label market:
    e "The market is full of colours today. Let's buy something nice."
    $ coins -= 1
    $ renpy.notify("You spent one coin.")
    m "Look at this lantern! It only costs [coins] coins, plus one for the delivery."
    e "100% worth it. Let's take it!"
    jump ending

label bridge:
    e "The bridge looks older than I remembered."
    m "{w}It's fine. Probably. Please don't jump on it."
    e "I wasn't going to... \"probably\"."
    jump ending

label home:
    "You decided to stay home and drink tea by the window."
    "Sometimes the best adventure is a quiet afternoon."
    jump ending

label ending:
    show screen help_hint
    e "Thank you for playing, [player_name]!"
    "The end."
    return
