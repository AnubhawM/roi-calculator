Web App Template

To run the application locally, follow these steps:

First, clone your repository using "git clone (repository-url)" and navigate to the project folder using "cd (repository-folder)". 

For the backend, navigate to the backend folder using "cd backend". Create a Conda environment using "conda create --name (env-name) python=3.12.1 -y" and activate it with "conda activate (env-name)". 

Install dependencies using "pip install -r requirements.txt" from the "backend" directory. 

Fill out secrets in the provided .env.template file and rename it to .env. 
.env files are in the .gitignore since they are not to be committed.

Run the Flask server using python app.py. 

If you are using GitHub Codespaces, make port 5000 public by opening the Ports tab in Codespaces, locating port 5000, and setting its visibility to Public. 

For the frontend, navigate to the frontend folder using cd ../frontend. 

Install dependencies with npm install. 

Fill out secrets in the provided .env.template file and rename it to .env. .env files are in the .gitignore since they are not to be committed. (Use the public URL provided by Codespaces for port 5000 if applicable). 

Start the React development server with npm run dev. 

If you are using GitHub Codespaces, make port 5173 public by opening the Ports tab, locating port 5173, and setting its visibility to Public. 

Access the application by opening your browser and navigating to http://localhost:5173 (or use the public URL provided by Codespaces for port 5173). 

If you want to deploy this project for free, deploy your frontend using Vercel or Netlify and deploy your backend using Render or Railway. 

You can set up Vercel deployment through Vercel's website or you can try from the terminal:

For Vercel, navigate to your frontend directory and run vercel (after installing Vercel CLI with npm install -g vercel). 

Follow the prompts to deploy and get a public URL. Set environment variables for your backend URL in Vercel's project settings. 

For Render, create a new web service linked to your GitHub repository containing the backend code, set Python as the environment, and add any environment variables.

Deploy and get a public URL for your backend. Update your frontend's .env file with this backend URL and redeploy your frontend. 

After deployment, test your application by accessing it via the frontend's public URL. 

If you encounter issues during deployment or testing, ensure that both frontend and backend URLs are correctly configured in their respective .env files and that CORS is properly handled in your backend code. Ensure that the correct URLs are being used in app.py and any axios calls (for example, make sure that you switch from localhost URLs to public URLs)

Mind the URLs in app.py and App.tsx. Depending on if you are doing local development or using URLs from the deployments, you need to change them in the code to avoid CORS issues. Add the URLs as an environment variable eventually so it's not hardcoded in the files.