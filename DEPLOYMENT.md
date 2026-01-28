# 🚀 Deploying Acoustic Fella to Railway

This guide will help you deploy your Acoustic Fella application to Railway, making it accessible from anywhere on the internet.

## What You Need

- [Railway account](https://railway.app) (free tier available)
- [GitHub account](https://github.com)
- Your Acoustic Fella code pushed to GitHub

## Deployment Files (Already Created)

Your project now includes these deployment files:

- ✅ **Procfile** - Tells Railway how to run your app
- ✅ **runtime.txt** - Specifies Python 3.13
- ✅ **requirements.txt** - Updated with gunicorn
- ✅ **railway.json** - Railway configuration
- ✅ **.railwayignore** - Files to exclude from deployment

## Step-by-Step Deployment

### Method 1: Deploy from GitHub (Recommended)

#### 1. Push Your Code to GitHub

```bash
# Initialize git (if not already done)
git init

# Add all files
git add .

# Commit
git commit -m "Prepare for Railway deployment"

# Add your GitHub repository
git remote add origin https://github.com/YOUR_USERNAME/acoustic-fella.git

# Push to GitHub
git push -u origin main
```

#### 2. Deploy on Railway

1. Go to [railway.app](https://railway.app)
2. Click **"Start a New Project"**
3. Select **"Deploy from GitHub repo"**
4. Choose your **acoustic-fella** repository
5. Railway will automatically:
   - Detect it's a Python project
   - Install dependencies from `requirements.txt`
   - Start the server using `gunicorn`
   - Generate a public URL

#### 3. Get Your Public URL

1. In your Railway project dashboard
2. Click on your deployment
3. Go to **"Settings"** tab
4. Under **"Domains"**, click **"Generate Domain"**
5. You'll get a URL like: `https://acoustic-fella-production.up.railway.app`

**That's it!** Your app is now live and accessible from anywhere! 🎉

### Method 2: Deploy from Railway CLI

#### 1. Install Railway CLI

```bash
# Using npm
npm install -g @railway/cli

# Or using curl (Linux/Mac)
curl -fsSL https://railway.app/install.sh | sh
```

#### 2. Login and Deploy

```bash
# Navigate to your project
cd C:\Users\S\Documents\ACFELLA

# Login to Railway
railway login

# Initialize Railway project
railway init

# Deploy (this will upload your code)
railway up

# Generate domain
railway domain
```

Your app will be deployed and you'll receive a public URL!

## Environment Variables (Optional)

If you need to set environment variables:

1. In Railway dashboard, go to your project
2. Click **"Variables"** tab
3. Add variables like:
   - `FLASK_ENV=production`
   - `SECRET_KEY=your-secret-key`

## Monitoring Your Deployment

### Check Logs
```bash
railway logs
```

Or view them in the Railway dashboard under the **"Deployments"** tab.

### View Build Output
Railway shows real-time build logs so you can see:
- Dependency installation
- Any errors
- Server startup

## Troubleshooting

### App Won't Start?
Check the logs:
```bash
railway logs
```

Common issues:
- Missing dependencies: Add them to `requirements.txt`
- Port binding: Gunicorn automatically uses `$PORT` from Railway
- Module imports: Make sure `__init__.py` files exist

### Build Failed?
- Verify `requirements.txt` has all dependencies
- Check Python version in `runtime.txt` (currently 3.13.0)
- Review build logs in Railway dashboard

### App is Slow?
Free tier limitations:
- 500 hours/month
- Sleeps after inactivity (first request takes ~30s)
- Upgrade to Hobby plan ($5/month) for always-on

## Updating Your Deployment

Every time you push to GitHub, Railway automatically rebuilds and redeploys:

```bash
# Make changes to your code
git add .
git commit -m "Updated hybrid panel feature"
git push

# Railway automatically deploys the new version!
```

## Cost

- **Free Tier**: 500 execution hours/month, $5 credit
- **Hobby**: $5/month for always-on service
- **Pro**: $20/month for production apps

Your Acoustic Fella app should work perfectly on the free tier!

## Custom Domain (Optional)

Want `acousticfella.com` instead of `*.railway.app`?

1. Buy a domain (Namecheap, GoDaddy, etc.)
2. In Railway, go to **Settings > Domains**
3. Click **"Custom Domain"**
4. Follow DNS setup instructions
5. Add CNAME record pointing to Railway

## Need Help?

- Railway Docs: https://docs.railway.app
- Railway Discord: https://discord.gg/railway
- Check Railway status: https://status.railway.app

---

**Your app is now accessible worldwide!** 🌍

Share your URL with clients, collaborators, or use it from any device!
