🎯 SniperBowlBot - Telegram Bot for Crypto Trading Competition 🎯

This bot helps track and manage a crypto trading competition where participants trade with their own wallets and compete for the best performance.

📋 COMMANDS:

1. /start - Start the bot and get welcome message
2. /help - Show help message with all commands
3. /rule - Show rules of the Sniper Bowl competition
4. /leaderboard - Show your personal picks leaderboard
5. /register_wallet - Register your wallet for the Sniper Bowl competition
6. /sniper_leaderboard - Show the overall Sniper Bowl leaderboard
7. /share - Share your picks on Twitter

📝 HOW TO USE:

1. REGISTERING YOUR WALLET:
   - Use /register_wallet command
   - Enter your Solana wallet address when prompted
   - The bot will track your wallet's performance
   - You can only register one wallet per user

2. TRACKING YOUR PICKS:
   - Simply paste a Solana token contract address (CA) in the chat
   - The bot will automatically track it with 0.5 SOL investment
   - Use /leaderboard to see your picks' performance
   - Use /share to share your performance on Twitter

3. COMPETITION RULES:
   - NO bots allowed for buying or selling
   - You can set stop losses or auto buys
   - NO buying promotions, ads, or boosts
   - You can post on X (Twitter) to promote yourself or coins
   - Must tag @CoinSnipersBowl in ALL posts
   - Only one fresh wallet per participant
   - Buying back in is allowed if you lose initial amount

⚠️ IMPORTANT NOTES:
- The bot tracks real-time prices and performance
- All trades must be done manually (no bots)
- Performance is calculated based on USD value
- Leaderboard updates in real-time
- Make sure to use a fresh wallet for the competition

🔧 TECHNICAL REQUIREMENTS:
- Python 3.11.7 or higher
- MongoDB database
- Telegram Bot Token
- Moralis API Key

🚀 RUNNING THE BOT:

   a. Clone the repository
   b. Create a .env file with the following variables:
      - TELEGRAM_BOT_TOKEN=your_bot_token
      - MONGODB_URI=your_mongodb_uri
      - API_KEY=your_moralis_api_key
   c. Install dependencies:
      pip install -r requirements.txt
   d. Run the bot:
      python bot.py

For any issues or questions, please contact the bot administrator. 