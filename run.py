
from bauhaus import Encoding, proposition, constraint
from bauhaus.utils import count_solutions, likelihood

# These two lines make sure a faster SAT solver is used.
from nnf import config
config.sat_backend = "kissat"

# Encoding that will store all of your constraints
E = Encoding()

# To create propositions, create classes for them first, annotated with "@proposition" and the Encoding
@proposition(E)
class BasicPropositions:

    def __init__(self, data):
        self.data = data

    def __repr__(self):
        return f"A.{self.data}"


# Different classes for propositions are useful because this allows for more dynamic constraint creation
# for propositions within that class. For example, you can enforce that "at least one" of the propositions
# that are instances of this class must be true by using a @constraint decorator.
# other options include: at most one, exactly one, at most k, and implies all.
# For a complete module reference, see https://bauhaus.readthedocs.io/en/latest/bauhaus.html
@constraint.at_least_one(E)
@proposition(E)
class FancyPropositions:

    def __init__(self, data):
        self.data = data

    def __repr__(self):
        return f"A.{self.data}"

# Call your variables whatever you want
#a = BasicPropositions("a")
#b = BasicPropositions("b")   
#c = BasicPropositions("c")
#d = BasicPropositions("d")
#e = BasicPropositions("e")
# At least one of these will be true
x = FancyPropositions("x")
y = FancyPropositions("y")
z = FancyPropositions("z")

board = []

# Build an example full theory for your setting and return it.
#
#  There should be at least 10 variables, and a sufficiently large formula to describe it (>50 operators).
#  This restriction is fairly minimal, and if there is any concern, reach out to the teaching staff to clarify
#  what the expectations are.
def example_theory():
    # Add custom constraints by creating formulas with the variables you created. 
    #E.add_constraint((a | b) & ~x)
    # Implication
    E.add_constraint(y >> z)
    # Negate a formula
    E.add_constraint(~(x & y))
    # You can also add more customized "fancy" constraints. Use case: you don't want to enforce "exactly one"
    # for every instance of BasicPropositions, but you want to enforce it for a, b, and c.:
    #constraint.add_exactly_one(E, a, b, c)

    # 2d array of dictionaries
    # row#, col#, color key
    colors = ["r", "g", "b", "y", "w", "b"]

    # Build propositions for every color in every peg of the board
    for row in range(0, 8):
        board.append([])
        for col in range(0, 4):
            board[row].append({})
            for color in colors:
                board[row][col][color] = BasicPropositions(f"X{row}{col}" + color)
            # Exactly one color can be present in a peg
            constraint.add_exactly_one(E, *board[row][col].values())

    # Define the contents of the first row
    E.add_constraint(board[0][0]["r"] & board[0][1]["w"] & board[0][2]["y"] & board[0][3]["g"])

    return E


if __name__ == "__main__":

    T = example_theory()
    # Don't compile until you're finished adding all your constraints!
    T = T.compile()
    # After compilation (and only after), you can check some of the properties
    # of your model:
    print("\nSatisfiable: %s" % T.satisfiable())
    print("# Solutions: %d" % count_solutions(T))
    print("   Solution: %s" % T.solve())

    print("\nVariable likelihoods:")
    for row in range(len(board)):
        for col in range(len(board[row])):
            for p in board[row][col].values():
                # Ensure that you only send these functions NNF formulas
                # Literals are compiled to NNF here
                print(" %s: %.2f" % (p, likelihood(T, p)))
    print()
