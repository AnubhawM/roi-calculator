# ValueVision

## Running the Application Locally

To run the application locally, follow these steps:

First, clone your repository using ```git clone (repository-url)``` and navigate to the project folder using ```cd (repository-folder)``` 

For the backend, navigate to the backend folder called ```backend```. Create a Conda environment using ```conda create --name (environment-name) python=3.12.1 -y``` and activate it with ```conda activate (environment-name)``` 

Install dependencies using ```pip install -r requirements.txt``` from the ```/backend``` directory

Fill out secrets in the provided ```.env.template``` file and rename it to ```.env```


Run the Flask server using ```python app.py``` 



For the frontend, navigate to the frontend folder called ```frontend``` 

Install dependencies with ```npm install``` 

Fill out secrets in the provided ```.env.template``` file and rename it to ```.env```

Start the React development server with ```npm run dev``` 

Run the command ```az login```. This will allow you to connect to your Azure account for credentials
If no web browser is available or the web browser fails to open, you may force device code flow with ```az login --use-device-code```

Access the application by opening your browser and navigating to http://localhost:5173 

## License

[MIT](https://choosealicense.com/licenses/mit/)