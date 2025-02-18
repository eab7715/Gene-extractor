
import argparse # Used to parse command-line arguments and helps make user-friendly command-line interfaces
import requests # Required to make HTTP requests (i.e. web scraping and API interactions in this case)
import json # Allows for the encoding/decoding of JSON type data (such as API requests)
from typing import List, Dict, Optional, Tuple # Just for better readability overall...
import sys  # This script requires access to certain system-specific parameters, such as sys.argv. sys gives access tu such parameters
import time # Allows the functions to work with time parameters (ex time.sleep() for delays and/or time.time() for timestamps
from bs4 import BeautifulSoup # The BeautifulSoup library is used for the parsing and web scraping of HTML documents
import re # Aids in pattern matching and text manipulation
from pathlib import Path # Allows the user to work with file paths in an object-oriented manner
import logging # Flexible framework for message logging (i.e. debugging and/or program execution tracking)
from urllib.parse import urljoin # This is a utility function. combines a base URL with a relative URL to form an executable absolute URL

# References for lines 20 through 70
# - https://www.geeksforgeeks.org/get-post-requests-using-python/
# - https://www.datacamp.com/tutorial/making-http-requests-in-python
# - https://www.datacamp.com/tutorial/python-api
# - https://www.dataquest.io/blog/api-in-python/

# We begin defining a python class called GeneReviewsExtractor...
class GeneReviewsExtractor:
    def __init__(self, cache_dir: Optional[Path] = None): # Which takes an optional argument (cache_dir) that allows us to specify a working directory for the retrieval of the cached data. Although not required, it ensures that a directory exists.
        self.base_medline_url = "https://medlineplus.gov/download/genetics"
        self.genereviews_base_url = "https://www.ncbi.nlm.nih.gov/books"
        self.genereviews_map_url = "https://ftp.ncbi.nih.gov/pub/GeneReviews/NBKid_shortname_genesymbol.txt" # The previous three lines define URL attributes regarding accessing medlineplus and ncbi databases, as well as to a gene symbol text mapping file
        self.nbk_to_gene_map = {} # Defining such an attribute allows for the creation of a dictionary to store such mapping
        self.gene_to_nbk_map = {}  # Stores multiple NBK IDs per gene
        self.cache_dir = cache_dir # This attribute stores the created directory path
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'GeneReviewsExtractor/1.0 (Educational Purpose)'
        }) # The previous three lines define attributes that create a request session in order to handle such HTTP requests as efficiently as possible. It also sets a custom User-Agent identity header to be able to rapidly identify the scraper

        # From this point, we can attempt to setup the logging process
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger(__name__) # This section of the script allows for both timestamps and log levels to be displayed for a more robust debugging approach. Essentially, we create a logger instance directly named after the script

        # Initialize cache directory if specified
        if cache_dir:
            cache_dir.mkdir(parents=True, exist_ok=True) # Essentially a failsafe. We ensure that the neccessary cache directory is present by creating it if it is not

        # This section of the script that deals with gene symbol mapping is considered to be a private method, meaning that the function is only to be used within it's specified class
        self._load_nbk_mapping()

    def _load_nbk_mapping(self):
        """Load the NBK ID to gene symbol mapping file with support for multiple diseases per gene""" # Here we initialize the demand to retrieve the mapping file from gene reviews
        try:
            response = self.session.get(self.genereviews_map_url)
            response.raise_for_status() # The previous three lines execute a HTTP GET request to try to obtain such a file. If the request were to fail, .raise_for_status() will flag an error. Although not required, it contributes to a robust debugging approach and makes the script more user-friendly

            for line in response.text.split('\n'):
                if line.strip():
                    parts = line.strip().split('\t')
                    if len(parts) >= 2:
                        nbk_id = parts[0]
                        genes = parts[2].split(';') if len(parts) > 2 else []
                        for gene in genes:
                            gene = gene.strip().upper()
                            if gene not in self.gene_to_nbk_map:
                                self.gene_to_nbk_map[gene] = []
                            self.gene_to_nbk_map[gene].append(nbk_id)
                            self.nbk_to_gene_map[nbk_id] = gene # The previous twelve lines allows the initialized HTTP GET request to parse the file line by line and extract relevant NBK IDs and Gene Symbols. From here, this mapping is then stored in self.nbk_to_gene_map by utilizing Gene Symbols (in uppercase) as keys

            self.logger.info(f"Loaded mappings for {len(self.gene_to_nbk_map)} genes") # Simply allows for the logging of the number of succesfuly loaded gene maps
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Error loading NBK mapping: {e}")
            raise # The previous three lines allow for both the appropriate handling and logging of HTTP GET request errors, should any arise

# References for lines 78 through 138
# - https://realpython.com/caching-external-api-requests/
# - https://requests-cache.readthedocs.io/en/v0.6.4/index.html
# - https://zenscrape.com/api-scraping-in-python-a-step-by-step-tutorial-for-beginners/
# - https://www.askpython.com/python/examples/pull-data-from-an-api

    def _get_cached_data(self, cache_key: str) -> Optional[Dict]:
        """Retrieve data from cache if available""" # In this function, we retrieve the previously saved JSON files from our cache
        if not self.cache_dir:
            return None # If there is no caching, return none

        cache_file = self.cache_dir / f"{cache_key}.json" # Creates a file path for the cached file
        if cache_file.exists(): # If such a cached file does exist...
            try:
                with cache_file.open('r') as f:
                    return json.load(f) # Load and return its cached JSON data
            except json.JSONDecodeError:
                return None # Or return none if the JSON data/file is corrupt
        return None # Also return none if no such cached file exists

    def _save_to_cache(self, cache_key: str, data: Dict):
        """Save data to cache""" # In this function, we allow for the saving of the JSON data to our cache file
        if not self.cache_dir:
            return # As a failsafe, do not return anything if caching is not enabled

        cache_file = self.cache_dir / f"{cache_key}.json" # Constructing the cache file path...
        with cache_file.open('w') as f:
            json.dump(data, f) # We write and save the data in JSON format

    def get_gene_info(self, gene: str) -> Optional[Dict]:
        """Get gene information from MedlinePlus Genetics API""" # It is within this function that we are able to initialize the API request and begin extracting gene information
        cache_key = f"gene_{gene}" # Let's generate a cache key based on the gene name that is being searched for
        cached_data = self._get_cached_data(cache_key) # If such data is already in a cached state...
        if cached_data:
            return cached_data # Simply return this data

        try:
            response = self.session.get(f"{self.base_medline_url}/gene/{gene}.json") # Otherwise, let's intialize a medline API request
            if response.status_code == 200: # An API request status codd of 200 indicates a succesful API request. Provided ONLY a code of 200 was received, we can proceed with the API request...
                data = response.json() # By converting the responses to a JSON data type...
                self._save_to_cache(cache_key, data) # Saving it in a cached format...
                return data # And returning the extracted data.
            return None # Only to be ran when the output code is anything OTHER than 200

        except requests.exceptions.RequestException as e: # As another failsafe, let's log all errors regarding API requests.
            self.logger.error(f"Error fetching gene info for {gene}: {e}") # Logs the error
            return None # And then returns none

    def _extract_text_from_section(self, soup: BeautifulSoup, section_title: str) -> str:
        """Extract text from a specific section of the GeneReviews document""" # Assuming the API request outputted a code of 200, we can now specify which sections of Text we want to extract from such an http mining attempt

        header = soup.find(lambda tag: tag.name in ['h2', 'h3', 'h4'] and
                                       section_title.lower() in tag.text.lower()) # Finds the relevant section header/headers...

        if not header:
            return "" # Returns an empty string if there are no such headers

        content = []
        current = header.find_next_sibling() # Makes sure that we extract all content until the next available header
        while current and current.name not in ['h2', 'h3', 'h4']:
            if current.name in ['p', 'ul', 'ol']:
                text = current.get_text(strip=True, separator=' ')
                if text:
                    content.append(text) # Specifically, we include all paragraphs, unordered lists, and ordered lists (hence the usage of p, ul, ol, h2, h3 and h4 search terms)
            current = current.find_next_sibling() # We then move to the following element

        return '\n\n'.join(content) # To then return all relevant extracted text in a formatted string

# References for lines 146 through 221
# - https://www.fernandomc.com/posts/using-requests-to-get-and-post/
# - https://realpython.com/api-integration-in-python/
# - https://docs.python.org/3/library/urllib.parse.html
# - https://rowelldionicio.com/parsing-json-with-python/

    def fetch_genereview_content(self, nbk_id: str) -> Optional[Dict]:
        """Fetch and parse GeneReviews content""" # Within this function, we use nbk id values to parse and fetch relevant gene info from the GeneReviews database
        cache_key = f"genereview_{nbk_id}" # We begin by generating a cache key...
        cached_data = self._get_cached_data(cache_key) # and checking if the requested data is already cached...
        if cached_data:
            return cached_data # and returning it if it is

        url = f"{self.genereviews_base_url}/{nbk_id}/" # For the data that is not already cached, we begin by creating the proper URL to connect to
        try:
            response = self.session.get(url) # This fetches the content from GeneReviews...
            response.raise_for_status() # and raises an error if there is one at this initial connection step

            # Parse the HTML content
            soup = BeautifulSoup(response.text, 'html.parser') # Provided there is no error, we can begin our parsing request using BeautifulSoup

            title = soup.find('title')     # Extracts disease name from title
            disease_name = title.text.split(' - ')[0] if title else "Unknown Disease"

            # Extract relevant sections
            sections = {
                "disease_name": disease_name,
                "clinical_characteristics": self._extract_text_from_section(
                    soup, "Clinical Characteristics"
                ),
                "evaluation_of_relatives": self._extract_text_from_section(
                    soup, "Evaluation of Relatives at Risk"
                ),
                "genetic_counseling": self._extract_text_from_section(
                    soup, "Genetic Counseling"
                )
            } # The previous eleven lines of script specify which of the relevant section to mine from the URL http request

            self._save_to_cache(cache_key, sections) # Assuming no error is raised, let's save these sections into our cache file...
            return sections # and then return the output

        except requests.exceptions.RequestException as e:
            self.logger.error(f"Error fetching GeneReviews content for {nbk_id}: {e}")
            return None # As a failsafe, let's log all fetching errors and then proceed to return none. An empty string could also be returned if the user preferred it

    def get_genereview_sections(self, gene: str) -> Dict:
        """Get relevant sections from GeneReviews for a given gene, including multiple diseases""" # If our previous function created the URL HTTP parsing request, it is within this current function that we fetch and parse data for a specific gene
        gene = gene.upper() # We standardize gene names to be uppercase (something we previously defined for efficiency in the beginning of this script)
        result = {
            "gene": gene,
            "diseases": [],
            "error": None
        } # The previous seven lines of script initializes an empty dictionary in which relevant extracted gene information will be stored for the searched gene/genes

        try:
            # Get all NBK IDs for the gene
            nbk_ids = self.gene_to_nbk_map.get(gene, []) # Let's begin by attempting to obtain the NBK ID for the gene in question from GeneReviews
            if not nbk_ids:
                result["error"] = f"No GeneReviews entries found for gene {gene}" # If an error is raised, print this line of text...
                return result # otherwise, return the NBK ID...

            # Fetch content for each NBK ID
            for nbk_id in nbk_ids:
                sections = self.fetch_genereview_content(nbk_id)  # Fetch content from GeneReviews
                if sections:
                    disease_entry = {
                        "nbk_id": nbk_id,
                        "disease_name": sections.get("disease_name", "Unknown Disease"),
                        "clinical_characteristics": sections.get("clinical_characteristics"),
                        "evaluation_of_relatives": sections.get("evaluation_of_relatives"),
                        "genetic_counseling": sections.get("genetic_counseling")
                    }
                    result["diseases"].append(disease_entry)

            if not result["diseases"]:
                result["error"] = f"Failed to fetch any GeneReviews content for {gene}" # The previous thirteen lines of script then used the found NBK ID to fetch and parse the GeneReviews database. From there, it updates the result dictionary with the relevant sections that we previously defined

        except Exception as e:
            result["error"] = str(e)
            self.logger.error(f"Error processing gene {gene}: {e}") # As another failsafe, these three lines of script both log the error and print an error statement for the user

        return result # Provided there were no errors, we return the newly updated result dictionary, which should contain all the required gene information

# References for lines 229 through 289
# - https://www.codecademy.com/learn/ext-courses/using-openai-apis-accessing-openai-apis-from-python?_gl=1*1at8pgd*_gcl_au*Mjc1Mjc5MjMyLjE3MzI4MDUwMDc.*_ga*MDI1MTI5ODM4MC4xNzMyODA1MDA0*_ga_3LRZM6TM9L*MTczOTc5MDUyMC45LjAuMTczOTc5MDUyMC42MC4wLjA.
# - https://realpython.com/python-main-function/
# - https://docs.python.org/3/library/__main__.html
# - https://www.w3schools.com/python/python_json.asp

def read_gene_list(file_path: str) -> List[str]: # Here we define the function that will allow for the processing of a file containing a gene list within the command line
    """Read gene symbols from a file, one per line"""
    with open(file_path, 'r') as f:
        return [line.strip() for line in f if line.strip()]


def main():
    parser = argparse.ArgumentParser(description='Extract GeneReviews information for genes')
    parser.add_argument('--genes', nargs='*', help='HGNC gene symbol(s)')
    parser.add_argument('--gene-file', '-f', help='File containing gene symbols (one per line)')
    parser.add_argument('--output', '-o', help='Output file (optional)')
    parser.add_argument('--cache-dir', help='Cache directory for storing retrieved data',
                        default='cache')
    args = parser.parse_args() # The previous seven lines of script allow for this program to be command line executable (via argparse). It also specifies that a gene name or file is required as input within the command line

    if not args.genes and not args.gene_file:
        parser.error("Either --genes or --gene-file must be provided")

    cache_dir = Path(args.cache_dir) # Here we use Path to setup a cross-compatible cache directory

    try:
        extractor = GeneReviewsExtractor(cache_dir=cache_dir)
        results = []

        genes = args.genes or [] # Processes genes from the provided command line arguments

        if args.gene_file:
            file_genes = read_gene_list(args.gene_file)
            genes.extend(file_genes) # Process genes from a file if one was provided in the command line

        genes = list(dict.fromkeys(genes)) # Removes duplicates while preserving order

        for gene in genes: # using the gene list specified as per the command line
            print(f"Processing gene: {gene}") # Allows command-line interaction for the user
            result = extractor.get_genereview_sections(gene)
            results.append(result)
            time.sleep(1)  # Adds a delay to avoid overwhelming the server

        # Output results
        output_data = {
            "genes_processed": len(results),
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "results": results
        } # The previous five lines of scripts indexes within the empty results dictionary the number of genes processed, the appropriate timestamps, and results extracted

        if args.output:
            output_path = Path(args.output)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with output_path.open('w', encoding='utf-8') as f:
                json.dump(output_data, f, indent=2, ensure_ascii=False)
            print(f"Results written to {args.output}") # This code block verifies that the parent directory exists and then saves the data to a JSON file...
        else:
            print(json.dumps(output_data, indent=2, ensure_ascii=False)) # otherwise it just prints the JSON output to the console

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1) # As a safefail, we print the error code 1 and we log the error if one arises


if __name__ == "__main__":
    main() # Essentially, we make sure that our main function runs only when it is called and not when it is imported!