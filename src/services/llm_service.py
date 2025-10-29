# src/services/llm_service.py

import os
from PIL import Image
import google.generativeai as genai
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from src.config import get_settings
from src.utils.logger import get_logger
from typing import Optional

# Get logger instance
logger = get_logger(__name__)

class LLMService:
    """
    A singleton service for interacting with Google's Generative AI models.
    """
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(LLMService, cls).__new__(cls)
            cls._instance._initialize()
        return cls._instance

    def _initialize(self):
        """Initializes the generative AI client and model."""
        try:
            self.settings = get_settings()
            api_key = self.settings.llm.api_key
            model_name = self.settings.llm.model_name

            if not api_key:
                raise ValueError("GOOGLE_API_KEY is not set in the configuration.")
            
            genai.configure(api_key=api_key)
            self.model = genai.GenerativeModel(model_name)
            logger.info(f"LLMService initialized successfully with model: {model_name}")
        except Exception as e:
            logger.error(f"Failed to initialize LLMService: {e}")
            raise

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        retry=retry_if_exception_type(Exception)
    )
    def generate_text(self, prompt: str) -> str:
        """
        Generates text content based on a given prompt.

        Args:
            prompt: The input prompt for the model.

        Returns:
            The generated text.
        
        Raises:
            ValueError: If the prompt is empty.
        """
        if not prompt:
            raise ValueError("Prompt cannot be empty.")
        
        try:
            logger.info("Generating text for the given prompt...")
            response = self.model.generate_content(prompt)
            logger.info("Successfully generated text.")
            return response.text
        except Exception as e:
            logger.error(f"Error generating text: {e}")
            raise

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        retry=retry_if_exception_type(Exception)
    )
    def generate_image_caption(self, image_path: str, prompt: Optional[str] = None) -> str:
        """
        Generates a caption for an image.

        Args:
            image_path: The file path to the image.
            prompt: An optional custom prompt.

        Returns:
            The generated caption for the image.
            
        Raises:
            FileNotFoundError: If the image file does not exist.
        """
        if not os.path.exists(image_path):
            raise FileNotFoundError(f"Image file not found at: {image_path}")

        try:
            logger.info(f"Generating caption for image: {image_path}...")
            img = Image.open(image_path)
            
            if prompt is None:
                prompt = "Describe the image in detail."

            response = self.model.generate_content([prompt, img])
            logger.info("Successfully generated image caption.")
            return response.text
        except Exception as e:
            logger.error(f"Error generating caption for {image_path}: {e}")
            raise

# Singleton instance for easy access
llm_service = LLMService()
