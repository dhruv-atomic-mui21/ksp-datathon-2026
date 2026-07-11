const path = require('path');
const https = require('https');
const fs = require('fs');

const cliDir = 'C:/Users/dhruv/AppData/Roaming/npm/node_modules/zcatalyst-cli';

// Import configuration store and decryption helper directly from CLI
const Store = require(path.join(cliDir, 'lib/util_modules/config-store')).default;
const Crypt = require(path.join(cliDir, 'lib/authentication/crypt')).default;

// Helper to make POST request
function postRequest(url, data) {
    return new Promise((resolve, reject) => {
        const u = new URL(url);
        const postData = typeof data === 'string' ? data : new URLSearchParams(data).toString();
        
        const options = {
            hostname: u.hostname,
            path: u.pathname + u.search,
            method: 'POST',
            headers: {
                'Content-Type': 'application/x-www-form-urlencoded',
                'Content-Length': Buffer.byteLength(postData)
            }
        };

        const req = https.request(options, (res) => {
            let body = '';
            res.on('data', chunk => body += chunk);
            res.on('end', () => resolve(JSON.parse(body)));
        });

        req.on('error', reject);
        req.write(postData);
        req.end();
    });
}

// Helper to make GET request
function getRequest(url, token) {
    return new Promise((resolve, reject) => {
        const u = new URL(url);
        const options = {
            hostname: u.hostname,
            path: u.pathname + u.search,
            method: 'GET',
            headers: {
                'Authorization': 'Bearer ' + token,
                'accept': 'application/vnd.catalyst.v2+json'
            }
        };

        const req = https.request(options, (res) => {
            let body = '';
            res.on('data', chunk => body += chunk);
            res.on('end', () => resolve(JSON.parse(body)));
        });

        req.on('error', reject);
        req.end();
    });
}

async function run() {
    try {
        console.log("Reading credentials...");
        const encryptedToken = Store.store.in.credential;
        if (!encryptedToken) {
            console.error("No India DC credential found in store!");
            return;
        }

        console.log("Decrypting credentials...");
        const crypt = new Crypt('ZC_TRAM');
        const tokenObj = crypt.decrypt(encryptedToken);
        
        const refreshToken = tokenObj.refresh_token;
        console.log("Token decrypted successfully!");

        // Hardcoded web client credentials from CLI auth constants
        const clientId = '1000.D5IIHDXSPN2MII26AD0V61I6RMVSNM';
        const clientSecret = '02ee875ecfc50573e5cc8d62916ad3077be20d0f42';

        console.log("Exchanging refresh token for access token...");
        const authRes = await postRequest('https://accounts.zoho.in/oauth/v2/token', {
            refresh_token: refreshToken,
            client_id: clientId,
            client_secret: clientSecret,
            grant_type: 'refresh_token'
        });

        if (!authRes.access_token) {
            console.error("Failed to retrieve access token:", authRes);
            return;
        }
        
        console.log("Access token retrieved! Querying runtimes...");
        const runtimesRes = await getRequest('https://api.catalyst.zoho.in/baas/get-details?feature_name=runtime', authRes.access_token);
        
        console.log("\n=========================================");
        console.log("Supported Runtimes for India Data Center:");
        console.log("=========================================");
        console.log(JSON.stringify(runtimesRes, null, 2));
    } catch (e) {
        console.error("Execution failed:", e);
    }
}

run();
