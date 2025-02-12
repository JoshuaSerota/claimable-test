import sys

sys.path.insert(1, '..')

import unittest
import process_drug_data


class ProcessDrugDataTest(unittest.TestCase):
    def test_text_extraction(self):
        """Test the basic text extraction function."""
        text = process_drug_data.extract_text_from_pdf("test_text.pdf")
        self.assertTrue("This is a test." in text)


if __name__ == '__main__':
    unittest.main()
