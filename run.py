
from bauhaus import Encoding, proposition, constraint
from bauhaus.utils import count_solutions, likelihood
from typing import List, Dict

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
        return f"X.{self.data}"

@proposition(E)
class GuessFeedbackPropositions:

    def __init__(self, data, in_correct_position):
        self.data = data
        self.in_correct_position = in_correct_position

    def __repr__(self):
        # In the physical game, a red feedback peg means that the color is in the correct position, 
        # and is white if the color is used in the solution but in a different position
        return f"{'R' if self.in_correct_position else 'W'}.{self.data}"

# Propositions for which colors comprise the game's answer
@proposition(E)
class AnswerPropositions:

    def __init__(self, data):
        self.data = data

    def __repr__(self):
        return f"C.{self.data}"

# Different classes for propositions are useful because this allows for more dynamic constraint creation
# for propositions within that class. For example, you can enforce that "at least one" of the propositions
# that are instances of this class must be true by using a @constraint decorator.
# other options include: at most one, exactly one, at most k, and implies all.
# For a complete module reference, see https://bauhaus.readthedocs.io/en/latest/bauhaus.html
""" @constraint.at_least_one(E)
@proposition(E)
class FancyPropositions:

    def __init__(self, data):
        self.data = data

    def __repr__(self):
        return f"A.{self.data}"
 """

rows = 8
cols = 4
board: List[List[Dict]] = []
# Array of dictonaries, 
correct_colors: List[Dict] = []

# 2 dimensional arrays representing whether a given peg matches the corresponsing position in the answer
# And whether a color is in the wrong positoin but present in the answer.
color_in_correct_position: List[List] = []
color_used_in_answer: List[List] = []

colors = ["r", "o", "y", "g", "b", "p", "w", "b"]

# Create a disjunction of every element in the input list
def or_all(list):
    result = None
    for item in list:
        # For the first element, just set it, but otherwise create the disjunction
        # (Don't assume the container supports indexing)
        result = (result | item) if result else item
    return result

# Create a conjunction of every element in the input list
def and_all(list):
    result = None
    for item in list:
        # For the first element, just set it, but otherwise create the conjunction
        # (Don't assume the container supports indexing)
        result = (result & item) if result else item
    return result


def build_correct_answer( *answer):

    for col in range(cols):
        correct_colors.append({})
        for color in colors:
            correct_colors[col][color] = AnswerPropositions(str(col) + color)
        # The answer has exactly one color for each peg
        constraint.add_exactly_one(E, *correct_colors[col].values())

    answer_constraint = correct_colors[0][answer[0]]
    for col in range(1, cols):
        answer_constraint &= correct_colors[col][colors[col]]
    # Save which colors make up the correct answer 
    E.add_constraint(answer_constraint)

    print("Correct answer is: " + " ".join(answer))
    
    # The constrain where no 2 answer colors can be the same is omitted
    # Because every proposition already has its value locked in.


# Build an example full theory for your setting and return it.
#
#  There should be at least 10 variables, and a sufficiently large formula to describe it (>50 operators).
#  This restriction is fairly minimal, and if there is any concern, reach out to the teaching staff to clarify
#  what the expectations are.
#
# allow_duplicate_colors allows reducing the problem space and adds another controllable factor for analyzing the model
def example_theory(allow_duplicate_colors=False):
    # Add custom constraints by creating formulas with the variables you created. 
    #E.add_constraint((a | b) & ~x)
    # Implication
    #E.add_constraint(y >> z)
    # Negate a formula
    #E.add_constraint(~(x & y))
    # You can also add more customized "fancy" constraints. Use case: you don't want to enforce "exactly one"
    # for every instance of BasicPropositions, but you want to enforce it for a, b, and c.:
    #constraint.add_exactly_one(E, a, b, c)

    build_correct_answer("r", "w", "g", "p")

    # 2d array of dictionaries
    # row#, col#, color key
    # Build propositions for every color in every peg of the board
    for row in range(0, rows):
        board.append([])
        for col in range(0, cols):
            board[row].append({})
            for color in colors:
                board[row][col][color] = BasicPropositions(f"{row}{col}" + color)
            # Exactly one color can be present in a peg
            constraint.add_at_most_one(E, *board[row][col].values())

        if not allow_duplicate_colors:
            # Prevent a guess from containing multiple pegs of the same color
            for color in colors:
                all_of_color_in_row = []
                for col in range(0, cols):
                    all_of_color_in_row.append(board[row][col][color])
                constraint.add_at_most_one(E, *all_of_color_in_row)

    # Generate propositions to provide feedback on whether colors are included in the 
    # answer and and whether they are in the correct position.
    
    for row in range(0, rows):
        color_in_correct_position.append([])
        color_used_in_answer.append([])
        for col in range(0, cols):
            color_in_correct_position[row].append(GuessFeedbackPropositions(str(row) + str(col), in_correct_position=True))
            color_used_in_answer[row].append(GuessFeedbackPropositions(str(row) + str(col), in_correct_position=False))
            #E.add_constraint(color_in_correct_position[row][col] | color_used_in_answer[row][col])

            # Generate constrains allowing that automatically determine how correct a guess is and provide feedback to the solver
            for color in colors:
                # Check whether the color in the guess matches the solution
                E.add_constraint((board[row][col][color] & correct_colors[col][color]) >> color_in_correct_position[row][col])
                # TODO: Constrains for when color is in the solution but not the correct position
                # TODO: Check game win conditon (A row has the correct color in every position)

    # Add the game win condition: a row must have every color in the correct position
    E.add_constraint(and_all(map(or_all, color_in_correct_position)))

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
