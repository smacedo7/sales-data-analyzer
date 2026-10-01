from sales_data_analyzer.domain.company import Company

if __name__ == '__main__':
    company1 = Company(name="rockstar", sector="games")
    print(company1.name)
    print(company1)
