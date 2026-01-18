# FOVThingDashboard

`docker-compose up --build`

And note that you might need to run `docker system prune -a` to clean up the docker images and containers on the 
droplet before re-running the `docker-compose up --build` command.

I should also add more memory to the swap for the build process. 


Or just run:
```
# Note: be sure to create .env files in the client and app directories set to localhost:8000
# in 1 terminal
cd client
npm install
npm start

# in a 2nd terminal
cd app
python main.py
```


## Notes 

**TODO**
- Add raising an error when we don't have any .env files! The code runs without them atm, but mysteriously doesn't work fully ofc! Or just works on a local network. I didn't notice this when setting up aviva.fovdashboard.com


## Instructions

From asking ChatGPT how to set it up and point it at aviva.fovdashboard.com

Here’s a step-by-step guide to setting up this GitHub project on a **DigitalOcean Droplet** and pointing it to **aviva.fovdashboard.com**.

---

## **1. Set Up DigitalOcean Droplet**
1. **Create a DigitalOcean Droplet**  
   - Choose **Ubuntu 22.04 LTS** as the operating system.
   - Select at least **2 vCPUs and 4GB RAM** for performance.
   - Enable **SSH authentication** for secure access.

2. **Connect to the Droplet**  
   ```bash
   ssh root@YOUR_DROPLET_IP
   ```
---


## **2. Install Docker & Docker Compose**
Run the following commands to install Docker and Docker Compose:

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y docker.io docker-compose
sudo systemctl enable docker
sudo systemctl start docker
```

Verify installation:
```bash
docker --version
docker-compose --version
```

---

## **3. Clone the GitHub Repository**
Replace `GITHUB_REPO_URL` with the actual repository URL:

```bash
git clone GITHUB_REPO_URL fovdashboard
cd fovdashboard
```

---

## **4. Set Up Environment Variables**
Create a `.env` file in `app/` and `client/` directories if needed:
```bash
nano app/.env
```
Add your API keys, database URL, etc., if required.

---

## **5. Build & Run Docker Containers**
Navigate to the project directory and start the services:
```bash
docker-compose up --build -d
```
This will:
- Build and start the **backend (FastAPI)**
- Build and start the **frontend (React)**
- Ensure both run inside Docker

To check if containers are running:
```bash
docker ps
```

---

## **6. Install & Configure Nginx**
Install Nginx:
```bash
sudo apt install -y nginx
```

Replace Nginx’s default config:
```bash
sudo nano /etc/nginx/sites-available/default
```
Paste the following updated configuration:
```nginx
server {
    server_name aviva.fovdashboard.com www.aviva.fovdashboard.com;

    # Proxy for React frontend
    location / {
        proxy_pass http://localhost:3000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # Proxy for FastAPI backend
    location /api/ {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # WebSockets for FastAPI
    location /ws {
        proxy_pass http://localhost:8000/ws;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    listen 443 ssl; # managed by Certbot
    ssl_certificate /etc/letsencrypt/live/aviva.fovdashboard.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/aviva.fovdashboard.com/privkey.pem;
    include /etc/letsencrypt/options-ssl-nginx.conf;
    ssl_dhparam /etc/letsencrypt/ssl-dhparams.pem;
}


server {
    listen 80;
    server_name aviva.fovdashboard.com www.aviva.fovdashboard.com;
    return 301 https://$host$request_uri;
}
```

Save and restart Nginx:
```bash
sudo systemctl restart nginx
```

---

## **7. Set Up a Domain with SSL (Let's Encrypt)**
### **Update DNS Records**
- Go to your domain registrar (e.g., Namecheap, GoDaddy).
- Create an **A record** pointing `aviva.fovdashboard.com` to your **Droplet’s IP**.

### **Install Certbot**
```bash
sudo apt install -y certbot python3-certbot-nginx
```

### **Generate SSL Certificate**
```bash
sudo certbot --nginx -d aviva.fovdashboard.com -d www.aviva.fovdashboard.com
```

### **Auto-Renew SSL**
```bash
sudo certbot renew --dry-run
```

---

## **8. Verify Everything is Running**
- **Check logs for errors**
  ```bash
  docker logs fov-frontend
  docker logs fov-backend
  sudo systemctl status nginx
  ```
- **Access the website**
  - Open `https://aviva.fovdashboard.com`
  - The frontend should load correctly.
- **Test API**
  ```bash
  curl -X GET https://aviva.fovdashboard.com/api/devices
  ```

---

### **9. (Optional) Enable Firewall**
To secure the server:
```bash
sudo ufw allow OpenSSH
sudo ufw allow 'Nginx Full'
sudo ufw enable
```

---

### 🎉 **Done!**  
Your project is now running on **DigitalOcean**, accessible at **https://aviva.fovdashboard.com** 🚀.
