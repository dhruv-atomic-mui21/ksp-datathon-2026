const path = require('path');
const fs = require('fs');

const cliDir = 'C:/Users/dhruv/AppData/Roaming/npm/node_modules/zcatalyst-cli';

// Initialize CLI configurations
const runtimeStore = require(path.join(cliDir, 'lib/runtime-store')).default;
const { detailsAPI } = require(path.join(cliDir, 'lib/endpoints'));

async function run() {
    try {
        // Read project credentials from local session
        const rcPath = 'c:/Users/dhruv/Desktop/datathon ksp/.catalystrc';
        if (!fs.existsSync(rcPath)) {
            console.error(".catalystrc not found at " + rcPath);
            return;
        }
        const rc = JSON.parse(fs.readFileSync(rcPath, 'utf8'));
        
        // Setup credentials store
        runtimeStore.set('project', rc.projects[0]);
        runtimeStore.set('env', rc.projects[0].env[0]);
        runtimeStore.set('dc', 'in'); // India Data Center
        
        // Query allowed runtimes
        const api = await detailsAPI();
        const details = await api.getDetails('runtime');
        console.log("Allowed Runtimes JSON:", JSON.stringify(details, null, 2));
    } catch (e) {
        console.error("Failed to fetch runtimes:", e);
    }
}

run();
