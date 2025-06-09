#!/usr/bin/env python3
import os
import re
import logging
import requests
from datetime import datetime, UTC
from urllib.parse import quote
from solders.pubkey import Pubkey
from moralis import sol_api
from dotenv import load_dotenv
from pymongo import MongoClient
from telegram import Update, Chat
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
    ConversationHandler,
)

# ==========================================
# 1. Load Environment Variables
# ==========================================
load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
MONGODB_URI = os.getenv("MONGODB_URI")
API_KEY = os.getenv("API_KEY")

if not TELEGRAM_BOT_TOKEN or not MONGODB_URI or not API_KEY:
    raise ValueError("Missing TELEGRAM_BOT_TOKEN or MONGODB_URI or API_KEY in .env")

# ==========================================
# 2. Logging Configuration
# ==========================================
# logging.basicConfig(
#     format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
#     level=logging.INFO
# )
logger = logging.getLogger(__name__)

# ==========================================
# 3. MongoDB Setup
# ==========================================
client = MongoClient(MONGODB_URI)
db = client["snipe_checks"]
picks_collection = db["picks"]     # For shilled CAs
wallets_collection = db["wallets"] # For sniper bowl wallets

# Ensure indexes
picks_collection.create_index(
    [("chat_id", 1), ("mint_address", 1)],
    unique=True,
    name="chat_mint_unique_index"
)

# ==========================================
# 4. API Calls
# ==========================================
def get_sol_price() -> float:
    url = "https://api.coingecko.com/api/v3/simple/price"
    params = {
        "ids": "solana",
        "vs_currencies": "usd"
        }
    try:
        response = requests.get(url, params=params)
        data = response.json()
        return (float(data["solana"]["usd"]))
    except Exception as e:
        logger.error(f"Error fetching SOL price: {e}")
        return 0.0

def get_sol_balance(wallet_address: str) -> float:
    params = {
        "network": "mainnet",
        "address": wallet_address
    }
    result = sol_api.account.balance(
        api_key=API_KEY,
        params=params,
    )
    return float(result.get("solana"))

def get_latest_close_price_in_sol(mint_address: str) -> float:
    try:
        params = {
            "network": "mainnet",
            "address": mint_address
        }
        result = sol_api.token.get_token_price(
            api_key=API_KEY,
            params=params,
        )
        price = float(result.get("nativePrice", {}).get("value", 0))/10**9
        return price
    except Exception as e:
        # logger.error(f"Error fetching token price for {mint_address}: {e}")
        return 0.0

def is_valid_solana_address(address: str) -> bool:
    # if len(address) not in [43, 44]:
    #     return False
    # pattern = r'^[1-9A-HJ-NP-Za-km-z]+$'
    # return bool(re.match(pattern, address))
    try:
        pubkey = Pubkey.from_string(address)
        # Optional: check if the pubkey is on the ed25519 curve
        flag=pubkey.is_on_curve()
        return flag
    except Exception:
        return False

def get_wallet_balances(wallet_address: str) -> dict:
    params = {
        "exclude_spam": False,
        "network": "mainnet",
        "address": wallet_address
    }

    result = sol_api.account.get_spl(
        api_key=API_KEY,
        params=params,
    )
    tokens=[]
    for i in result:
        tokens.append({"mint":i.get("mint"),"amount":i.get("amount")})
    return tokens

def get_tiker(wallet_address: str) -> str:
    try:
        url = f"https://solana-gateway.moralis.io/token/mainnet/{wallet_address}/metadata"
        headers = {
            "Accept": "application/json",
            "X-API-Key": API_KEY
        }
        response = requests.request("GET", url, headers=headers)
        if response.status_code == 200:
            return response.json().get("symbol", "N/A")
        return "N/A"
    except Exception as e:
        logger.error(f"Error fetching token metadata for {wallet_address}: {e}")
        return "N/A"


# ==========================================
# 5. Bot Handlers
# ==========================================

# ------------ HELP & START ------------
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /start - Simplified welcome message with emojis.
    """
    welcome_text = (
        "🎯 👋 *Welcome to the SniperBowlBot!*\n\n"
        "You a Coin Sniping All Star?\n\n"
        "This Bot lets you find out who is the best trader. No bots to do the buying or selling. Human hands only! (CHEATERS WILL NOT WIN. IF YOUR BUYING AND SELLING LOOKS EVEN REMOTELY SUSPICIOUS YOU WILL BE DISQUALIFIED) \n\n"
        "*Register your fresh wallet with no transactions. (/register_wallet)*\n\n"
        "Use that wallet to buy 0.5 SOL (or the agreed upon contest starting amount) and trade.\n"
        "We'll track your real PnL.\n\n"
        "Type /help for commands.\n"
        "Enjoy! 🚀"
    )
    await update.message.reply_text(welcome_text, parse_mode="Markdown")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /help - Shows usage and commands with emojis.
    """
    help_text = (
        "🆘 *SniperBowlBot Help* \\(/start\\)\n\n"
        "\\(Function 1\\)\n"
        "• /register\\_wallet – Register your fresh wallet with only your contest trading amount for a Sniper Bowl in it \\(Rebuy as many times as you like\\)\n\n"
        "\\(Function 2\\)\n\n"
        "• /sniper\\_leaderboard – Shows the Sniper Bowl leaderboard for the contest \\(wallet\\-based\\. The team wonky will post the leaderboard during competitions\\)\n"
        # "• /share – Share your CA picks on Twitter\n\n"
    )
    await update.message.reply_text(help_text, parse_mode="MarkdownV2")

async def rule_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    rule_text = (
        "🎯 *RULES*\n\n"
        "*NO* Bots To Do Buying or Selling\\.\n\n"
        "You can set stop losses or auto buys\\.\n\n"
        "*NO* buying promotions, ads, boosts, or anything other than the coins themselves\\. \n\n"
        "You can post on any x page to promote yourself or a coin you bought\\. \n"
        "*You MUST tag @CoinSniperBowl in ALL posts so everyone can track each others actions\\.*\n\n"
        "1 FRESH wallet only will be counted\\. \\(Buying back in if you lose the intial \\.5 or other agreed initial bag is allowed as many times as you want\\. MUST be on the same wallet\\)\n\n"
        "WE WANT TO TURN THIS INTO THE SUPER BOWL FOR CRYPTO TRADING\\.\n\n"
        "*LET THE GAMES BEGIN\\!*"
    )
    await update.message.reply_text(rule_text, parse_mode="MarkdownV2")

# ------------ FUNCTION 1: SHILLING CAs ------------
async def leader_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    sol_price = get_sol_price()
    if sol_price <= 0:
        await update.message.reply_text("❌ Could not fetch SOL price. Leaderboard unavailable.")
        return

    all_picks = list(picks_collection.find({"chat_id": chat_id}))
    if not all_picks:
        await update.message.reply_text("No CA picks found. Paste a CA to add your first pick!")
        return

    data_list = []
    for pick in all_picks:
        mint = pick["mint_address"]
        cost_basis_usd = pick["cost_basis_usd"]
        num_tokens = pick["num_tokens"]
        username = pick["username"]
        pick_user_id=pick["user_id"]

        current_close_sol = get_latest_close_price_in_sol(mint)
        if current_close_sol <= 0:
            continue  # Skip tokens with invalid prices

        current_token_price_usd = current_close_sol * sol_price
        current_value_usd = num_tokens * current_token_price_usd
        pnl = current_value_usd - cost_basis_usd

        if(pick_user_id==user_id):
            data_list.append({
                "username": username,
                "tiker": get_tiker(mint),
                "mint": mint,
                "cost_basis_usd": cost_basis_usd,
                "current_price_usd": current_token_price_usd,
                "pnl": pnl
            })

    if not data_list:
        await update.message.reply_text("No valid picks found with current price data.")
        return

    data_list.sort(key=lambda x: x["pnl"], reverse=True)
    result_text = "🏆 *Your Picks Leaderboard:* 🏆\n\n"
    for rank, item in enumerate(data_list[:10], start=1):
        sign = "+" if item["pnl"] >= 0 else "-"
        abs_pnl = abs(item["pnl"])
        result_text += (
            f"{rank}. {item['tiker']}\n"
            # f" Ticker: `{item['tiker']}`\n"
            f" Mint:`{item['mint']}`\n"
            f" PnL: {sign}${abs_pnl:,.2f}\n"
            f" Entry(0.5 SOL in USD): ${item['cost_basis_usd']:.2f}\n"
            f" Current Token Price: ${item['current_price_usd']:.8f}\n\n"
        )

    await update.message.reply_text(result_text, parse_mode="Markdown")

# ------------ FUNCTION 2: SNIPER BOWL ------------
WALLET_ADDRESS = 0

async def register_wallet_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start the wallet registration process."""
    await update.message.reply_text(
        "Please enter your Solana wallet address:"
    )
    return WALLET_ADDRESS

async def handle_wallet_address(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle the wallet address input."""
    if not update.message or not update.message.text:
        return ConversationHandler.END

    wallet_address = update.message.text.strip()
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    username = update.effective_user.username or "Anonymous"

    if not is_valid_solana_address(wallet_address):
        await update.message.reply_text("❌ Invalid Solana address. Please try again with /register_wallet")
        return ConversationHandler.END
    existing = wallets_collection.find_one({"chat_id": chat_id, "wallet_address": wallet_address})
    if existing:
        await update.message.reply_text("🎯 This wallet is already registered in this group.")
        return ConversationHandler.END
    register_existing = wallets_collection.find_one({"chat_id": chat_id, "user_id": user_id})
    if register_existing:
        await update.message.reply_text("🎯 You already registered your wallet.")
        return ConversationHandler.END

    sol_price = get_sol_price()
    sol_balance = get_sol_balance(wallet_address)
    if sol_price <= 0:
        await update.message.reply_text("❌ Could not fetch SOL price. Try again later.")
        return ConversationHandler.END
    
    # await update.message.reply_text("🎯 Oh, you think you a Sniper Bowl All Star. Okay, your results are being tallied and will be posted to you shortly.")

    balances = get_wallet_balances(wallet_address)

    total_usd = 0.0
    for token_info in balances:
        token_price = get_latest_close_price_in_sol(token_info.get("mint")) * sol_price
        token_balance = float(token_info.get("amount", 0))
        total_usd += token_balance * token_price

    start_usd_value = sol_balance * sol_price + total_usd

    doc = {
        "chat_id": chat_id,
        "user_id": user_id,
        "username": username,
        "wallet_address": wallet_address,
        "start_usd_value": start_usd_value,
        "created_at": datetime.now(UTC)
    }
    try:
        wallets_collection.insert_one(doc)
        await update.message.reply_text(
            "✅ Successfully registered your wallet"
        )

    except Exception as e:
        logger.error(f"Error registering wallet: {e}")
        await update.message.reply_text("❌ Could not register wallet. Please try again later.")
    
    return ConversationHandler.END

async def sniper_leaderboard_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    sol_price = get_sol_price()
    if sol_price <= 0:
        await update.message.reply_text("❌ Could not fetch SOL price. Leaderboard unavailable.")
        return

    all_wallets = list(wallets_collection.find({"chat_id": chat_id}))
    if not all_wallets:
        await update.message.reply_text("No wallets here. Use /register_wallet <address> to join!")
        return

    await update.message.reply_text("🎯 Oh, you think you a Sniper Bowl All Star. Okay, your results are being tallied and will be posted to you shortly.")

    results = []

    for w in all_wallets:
        user_name = w["username"]
        wallet_address = w["wallet_address"]
        start_usd_value = w["start_usd_value"]

        balances = get_wallet_balances(wallet_address)
        sol_balance = get_sol_balance(wallet_address)

        total_usd = sol_balance * sol_price
        for token_info in balances:
            token_price = get_latest_close_price_in_sol(token_info.get("mint")) * sol_price
            token_balance = float(token_info.get("amount", 0))
            total_usd += token_balance * token_price

        pnl_usd = total_usd - start_usd_value

        results.append({
            "username": user_name,
            "wallet_address": wallet_address,
            "net_worth_usd": total_usd,
            "pnl_usd": pnl_usd
        })

    results.sort(key=lambda x: x["pnl_usd"], reverse=True)

    result_text = "🏆 *Sniper Bowl Leaderboard:* 🏆\n\n"
    for rank, item in enumerate(results[:10], start=1):
        sign = "+" if item["pnl_usd"] >= 0 else "-"
        abs_pnl = abs(item["pnl_usd"])
        result_text += (
            f"{rank}. {item['username']} (Wallet: `{item['wallet_address']}`)\n"
            f"   Net Worth: ${item['net_worth_usd']:.2f}\n"
            f"   PnL: {sign}${abs_pnl:,.2f}\n\n"
        )

    await update.message.reply_text(result_text, parse_mode="Markdown")

# ------------ /share ------------
async def share_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    username = update.effective_user.username or "Anonymous"

    user_picks = list(picks_collection.find({"chat_id": chat_id, "user_id": user_id}))
    if not user_picks:
        await update.message.reply_text("No CA picks found for you here. Paste a CA first!")
        return

    sol_price = get_sol_price()
    if sol_price <= 0:
        await update.message.reply_text("Error fetching SOL price. Try again later.")
        return

    lines = []
    total_pnl = 0.0

    for pick in user_picks:
        mint = pick["mint_address"]
        cost_basis_usd = pick["cost_basis_usd"]
        num_tokens = pick["num_tokens"]
        tiker=get_tiker(mint)

        current_close_sol = get_latest_close_price_in_sol(mint)
        current_price_usd = current_close_sol * sol_price
        current_value_usd = num_tokens * current_price_usd
        pnl = current_value_usd - cost_basis_usd
        total_pnl += pnl

        sign = "+" if pnl >= 0 else "-"
        abs_pnl = abs(pnl)
        lines.append(f"{tiker} => {sign}${abs_pnl:,.2f}")

    sign_total = "+" if total_pnl >= 0 else "-"
    abs_total = abs(total_pnl)

    tweet_text = (
        f"{username}'s Picks:\n\n"
        + "\n".join(lines)
        + f"\n\nTotal PnL: {sign_total}${abs_total:,.2f}\n"
        "Shared via #Sniperbowlbot"
    )
    encoded_tweet = quote(tweet_text)
    twitter_link = f"https://twitter.com/intent/tweet?text={encoded_tweet}"

    msg = (
        f"🔗 Share your picks on Twitter:\n\n"
        f"[Click Here to Tweet]({twitter_link})"
    )
    await update.message.reply_text(msg, parse_mode="Markdown", disable_web_page_preview=True)
    #print("tweet:",encoded_tweet);

# ------------ Catch CA or fallback ------------
async def handle_contract_address(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return
    text = update.message.text.strip()
    if not is_valid_solana_address(text):
        # await fallback_echo(update, context)
        return

    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    username = update.effective_user.username or "Anonymous"
    mint_address = text

    existing_pick = picks_collection.find_one({"chat_id": chat_id, "mint_address": mint_address})
    if existing_pick:
        await update.message.reply_text(f"🎯 This CA was already shilled here: {mint_address}")
        return

    sol_price = get_sol_price()
    if sol_price <= 0:
        await update.message.reply_text("Error: Could not fetch SOL price. Try again later.")
        return

    try:
        close_price_sol = get_latest_close_price_in_sol(mint_address)
        if close_price_sol <= 0:
            await update.message.reply_text(f"❌ Could not fetch price for this token. It might be too new or invalid.")
            return
    except Exception as e:
        await update.message.reply_text(f"❌ Could not fetch price for this token. It might be too new or invalid.")
        return

    cost_basis_usd = 0.5 * sol_price
    num_tokens = 0.5 / close_price_sol

    pick_doc = {
        "chat_id": chat_id,
        "user_id": user_id,
        "username": username,
        "mint_address": mint_address,
        "cost_basis_usd": cost_basis_usd,
        "num_tokens": num_tokens,
        "created_at": datetime.now(UTC)
    }
    try:
        picks_collection.insert_one(pick_doc)
    except Exception as e:
        logger.error(f"Error inserting pick: {e}")
        await update.message.reply_text("❌ Could not add your pick. Possibly a duplicate or DB error.")
        return

    reply_text = (
        f"✅ Added your pick for CA: {mint_address}\n"
        f"Invested: 0.5 SOL (~${cost_basis_usd:.2f})\n"
        f"Received ~{num_tokens:.4f} tokens.\n"
    )
    await update.message.reply_text(reply_text)

# async def fallback_echo(update: Update, context: ContextTypes.DEFAULT_TYPE):
#     """Fallback echo if text is not recognized as CA/command."""
#     await update.message.reply_text(f"You said: {update.message.text}")

# ==========================================
# 6. Main
# ==========================================
def main():
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

    # Set up command descriptions
    commands = [
        ("start", "Start the bot and get welcome message"),
        ("help", "Show help message with all commands"),
        ("rules", "Show rules of usage Sniper Bowl"),
        ("my_calls", "Show shilled CA leaderboard"),
        ("register_wallet", "Register wallet for Sniper Bowl"),
        ("sniper_leaderboard", "Show Sniper Bowl leaderboard"),
        ("share", "Share your picks on Twitter")
    ]
    
    # Commands
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("rules", rule_command))
    app.add_handler(CommandHandler("my_calls", leader_command))
    
    # Add conversation handler for wallet registration
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("register_wallet", register_wallet_command)],
        states={
            WALLET_ADDRESS: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_wallet_address)],
        },
        fallbacks=[],
    )
    app.add_handler(conv_handler)
    
    app.add_handler(CommandHandler("sniper_leaderboard", sniper_leaderboard_command))
    app.add_handler(CommandHandler("share", share_command))

    # Handle text -> either valid CA or fallback
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_contract_address))

    logger.info("Starting Snipe Checks Bot with MongoDB persistence...")
    
    # Set commands and start polling
    app.bot.set_my_commands(commands)
    app.run_polling()


if __name__ == "__main__":
    main()
