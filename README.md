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